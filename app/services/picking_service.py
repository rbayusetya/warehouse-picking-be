from __future__ import annotations
import copy
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PickingList, PickingItem, PickingItemDealer, Settlement,
    SettlementHandover, HistoryEntry, Handover, DealerConfirmation, DealerReturn,
)
from app.services import s3_service

# Import the shared Excel parser
from picking_excel import parse_picking_workbook  # noqa: E402


def _now_text() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


async def import_excel(db: AsyncSession, file_path: str, filename: str, uploaded_by: str) -> list[dict]:
    parsed = parse_picking_workbook(file_path)

    for list_data in parsed:
        picking_list = PickingList(
            picking_id=list_data["id"],
            date=list_data["date"],
            no_ds=list_data.get("noDs", ""),
            expedition=list_data["expedition"],
            plate=list_data.get("plate", ""),
            driver=list_data["driver"],
            status="draft",
            source_file=filename,
        )

        history_entry = HistoryEntry(
            picking_list=picking_list,
            at=_now_text(),
            by=uploaded_by,
            text=f"Data picking diimpor dari Excel. No Picking List {list_data['id']}.",
        )
        picking_list.history.append(history_entry)

        for item_data in list_data["items"]:
            item = PickingItem(
                picking_list=picking_list,
                code=item_data["code"],
                name=item_data["name"],
                category=item_data["category"],
                planned_qty=item_data["plannedQty"],
                actual_qty=0,
                confirmed=False,
                note="",
            )

            for dealer_data in item_data.get("dealers", []):
                dealer = PickingItemDealer(
                    item=item,
                    no_so=dealer_data.get("noSo", ""),
                    code=dealer_data["code"],
                    dealer=dealer_data["dealer"],
                    qty=dealer_data["qty"],
                )
                item.dealers.append(dealer)

            picking_list.items.append(item)

        db.add(picking_list)

    await db.commit()
    return parsed


async def get_picking_lists(
    db: AsyncSession,
    user_role: str,
    user_expedition: str | None,
    user_dealer_code: str | None,
) -> list[PickingList]:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(PickingList)
        .options(
            selectinload(PickingList.items).selectinload(PickingItem.dealers),
            selectinload(PickingList.items).selectinload(PickingItem.settlements),
            selectinload(PickingList.items).selectinload(PickingItem.dealer_confirmations)
            .selectinload(DealerConfirmation.return_record),
            selectinload(PickingList.handover),
            selectinload(PickingList.history),
        )
        .order_by(PickingList.created_at.desc())
    )

    if user_role == "ekspedisi" and user_expedition:
        stmt = stmt.where(PickingList.expedition == user_expedition)
    elif user_role == "dealer" and user_dealer_code:
        stmt = stmt.where(
            PickingList.items.any(
                PickingItem.dealers.any(PickingItemDealer.code == user_dealer_code)
            )
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_picking_list(db: AsyncSession, list_id: str) -> PickingList | None:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(PickingList)
        .options(
            selectinload(PickingList.items).selectinload(PickingItem.dealers),
            selectinload(PickingList.items).selectinload(PickingItem.settlements),
            selectinload(PickingList.items).selectinload(PickingItem.dealer_confirmations)
            .selectinload(DealerConfirmation.return_record),
            selectinload(PickingList.handover),
            selectinload(PickingList.history),
        )
        .where(PickingList.picking_id == list_id)
        .order_by(PickingList.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_picking_items(
    db: AsyncSession,
    list_id: str,
    items_data: list[dict],
    user_name: str,
) -> PickingList | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list:
        return None

    for update in items_data:
        item_id = update.get("id")
        if not item_id:
            continue
        item = next((i for i in picking_list.items if i.id == item_id), None)
        if not item:
            continue

        if "confirmed" in update:
            item.confirmed = bool(update["confirmed"])
        if "actual_qty" in update:
            prev = item.actual_qty
            item.actual_qty = float(update["actual_qty"])
            if picking_list.status == "picked" and prev != item.actual_qty:
                picking_list.history.append(HistoryEntry(
                    at=_now_text(), by=user_name,
                    text=f"Revisi aktual {item.name}: {prev} menjadi {item.actual_qty}.",
                ))
        if "note" in update:
            prev_note = item.note
            item.note = update["note"]
            if picking_list.status == "picked" and prev_note != item.note:
                picking_list.history.append(HistoryEntry(
                    at=_now_text(), by=user_name,
                    text=f"Revisi notes {item.name}.",
                ))

    picking_list.updated_at = datetime.utcnow()
    await db.commit()
    return picking_list


async def complete_picking(db: AsyncSession, list_id: str, user_name: str) -> dict | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list:
        return None

    unconfirmed = [i for i in picking_list.items if not i.confirmed]
    if unconfirmed:
        return {"error": f"Masih ada {len(unconfirmed)} item belum dicentang."}

    missing_notes = [
        i.name for i in picking_list.items
        if i.actual_qty < i.planned_qty and not i.note.strip()
    ]
    if missing_notes:
        return {"error": "Notes wajib untuk: " + ", ".join(missing_notes[:5])}

    picking_list.status = "picked"
    planned = sum(i.planned_qty for i in picking_list.items)
    actual = sum(i.actual_qty for i in picking_list.items)
    debt = max(planned - actual, 0)
    text = f"Picking selesai dengan hutang {debt} qty." if debt else "Picking selesai lengkap."
    picking_list.history.append(HistoryEntry(at=_now_text(), by=user_name, text=text))
    picking_list.updated_at = datetime.utcnow()

    await db.commit()
    return {"status": "ok", "debt": debt}


async def create_handover(
    db: AsyncSession, list_id: str, data: dict, user_name: str
) -> Handover | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list or picking_list.status != "picked":
        return None

    signature_admin_url = None
    signature_driver_url = None
    if data.get("signature_admin"):
        signature_admin_url = s3_service.upload_base64_to_s3(
            data["signature_admin"], f"signatures/{picking_list.id}_admin_{_now_text().replace('/', '-')}.png", "image/png"
        )
    if data.get("signature_driver"):
        signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"], f"signatures/{picking_list.id}_driver_{_now_text().replace('/', '-')}.png", "image/png"
        )

    handover = Handover(
        picking_list_id=picking_list.id,
        admin_name=data["admin_name"],
        driver_name=data["driver_name"],
        signature_admin_url=signature_admin_url,
        signature_driver_url=signature_driver_url,
        created_by=user_name,
        created_at=_now_text(),
    )
    db.add(handover)

    planned = sum(i.planned_qty for i in picking_list.items)
    actual = sum(i.actual_qty for i in picking_list.items)
    paid = sum(
        sum(s.qty for s in i.settlements)
        for i in picking_list.items
    )
    debt = max(planned - actual - paid, 0)
    text = f"Serah terima selesai dengan hutang {debt} qty." if debt else "Serah terima selesai lengkap."
    picking_list.history.append(HistoryEntry(at=_now_text(), by=user_name, text=text))
    picking_list.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(handover)
    return handover


async def list_debts(
    db: AsyncSession,
    user_role: str,
    user_expedition: str | None,
    user_dealer_code: str | None,
) -> list[dict]:
    lists = await get_picking_lists(db, user_role, user_expedition, user_dealer_code)
    results = []
    for pl in lists:
        for item in pl.items:
            paid = sum(s.qty for s in item.settlements)
            debt_active = pl.status in ("picked",) or bool(pl.handover)
            if not debt_active:
                continue
            debt = max(item.planned_qty - item.actual_qty - paid, 0)
            if paid > 0 or debt > 0:
                results.append({
                    "picking_list": pl,
                    "item": item,
                    "paid": paid,
                    "debt": debt,
                })
    return results


async def create_settlement(
    db: AsyncSession, picking_item_id: str, qty: float, date: str,
    driver: str, note: str, user_name: str,
) -> Settlement | None:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(PickingItem)
        .options(
            selectinload(PickingItem.picking_list).selectinload(PickingList.history),
        )
        .where(PickingItem.id == picking_item_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        return None

    settlement = Settlement(
        picking_item_id=picking_item_id,
        qty=qty,
        date=date,
        driver=driver,
        note=note,
        by=user_name,
        at=_now_text(),
    )
    db.add(settlement)

    picking_list = item.picking_list
    picking_list.history.append(HistoryEntry(
        at=_now_text(), by=user_name,
        text=f"Pembayaran hutang {item.name} sebanyak {qty} qty dibawa {driver}.",
    ))
    picking_list.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(settlement)
    return settlement


async def create_settlement_handover(
    db: AsyncSession, settlement_id: str, data: dict, user_name: str,
) -> SettlementHandover | None:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(Settlement)
        .options(
            selectinload(Settlement.handover),
            selectinload(Settlement.item).selectinload(PickingItem.picking_list).selectinload(PickingList.history),
        )
        .where(Settlement.id == settlement_id)
    )
    result = await db.execute(stmt)
    settlement = result.scalar_one_or_none()
    if not settlement or settlement.handover:
        return None

    signature_admin_url = None
    signature_driver_url = None
    if data.get("signature_admin"):
        signature_admin_url = s3_service.upload_base64_to_s3(
            data["signature_admin"], f"settlement-signatures/{settlement_id}_admin_{_now_text().replace('/', '-')}.png", "image/png"
        )
    if data.get("signature_driver"):
        signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"], f"settlement-signatures/{settlement_id}_driver_{_now_text().replace('/', '-')}.png", "image/png"
        )

    handover = SettlementHandover(
        settlement_id=settlement_id,
        admin_name=data["admin_name"],
        driver_name=data["driver_name"],
        signature_admin_url=signature_admin_url,
        signature_driver_url=signature_driver_url,
        created_by=user_name,
        created_at=_now_text(),
    )
    db.add(handover)

    picking_list = settlement.item.picking_list
    picking_list.history.append(HistoryEntry(
        at=_now_text(), by=user_name,
        text=f"Serah terima pembayaran hutang {settlement.item.name} {settlement.qty} qty oleh admin {data['admin_name']}, driver {data['driver_name']}.",
    ))
    picking_list.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(handover)
    return handover


async def list_settlement_handovers(
    db: AsyncSession, user_role: str, user_expedition: str | None, user_dealer_code: str | None,
) -> list[SettlementHandover]:
    from sqlalchemy.orm import selectinload

    stmt = (
        select(SettlementHandover)
        .options(
            selectinload(SettlementHandover.settlement).selectinload(Settlement.item).selectinload(PickingItem.picking_list),
        )
        .order_by(SettlementHandover.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_dealer_items(db: AsyncSession, dealer_code: str) -> list[dict]:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(PickingItem)
        .options(
            selectinload(PickingItem.picking_list),
            selectinload(PickingItem.dealers),
            selectinload(PickingItem.settlements),
            selectinload(PickingItem.dealer_confirmations)
            .selectinload(DealerConfirmation.return_record),
        )
        .join(PickingItemDealer)
        .where(PickingItemDealer.code == dealer_code)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    output = []
    for item in items:
        pl = item.picking_list
        dealer_info = next((d for d in item.dealers if d.code == dealer_code), None)
        if not dealer_info:
            continue
        conf = next((c for c in item.dealer_confirmations if c.dealer_code == dealer_code), None)
        output.append({
            "picking_list_id": pl.id,
            "picking_id": pl.picking_id,
            "date": pl.date,
            "driver": pl.driver,
            "expedition": pl.expedition,
            "item_id": item.id,
            "item_name": item.name,
            "item_code": item.code,
            "item_category": item.category,
            "planned_qty": item.planned_qty,
            "actual_qty": item.actual_qty,
            "note": item.note,
            "dealer_code": dealer_code,
            "dealer_name": dealer_info.dealer,
            "dealer_qty": dealer_info.qty,
            "confirmation_status": conf.status if conf else None,
            "settlements": [{"qty": s.qty, "date": s.date, "driver": s.driver, "note": s.note, "by": s.by} for s in item.settlements],
        })
    return output


async def create_dealer_confirmation(
    db: AsyncSession, data: dict, user_name: str,
) -> DealerConfirmation | None:
    from sqlalchemy.orm import selectinload
    stmt = (
        select(PickingItem)
        .options(selectinload(PickingItem.picking_list))
        .where(PickingItem.id == data["picking_item_id"])
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        return None

    signature_dealer_url = None
    signature_driver_url = None
    if data.get("signature_dealer"):
        signature_dealer_url = s3_service.upload_base64_to_s3(
            data["signature_dealer"],
            f"dealer_sig/{data['picking_item_id']}_{data['dealer_code']}_dealer.png",
        )
    if data.get("signature_driver"):
        signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"],
            f"dealer_sig/{data['picking_item_id']}_{data['dealer_code']}_driver.png",
        )

    confirmation = DealerConfirmation(
        picking_item_id=data["picking_item_id"],
        dealer_code=data["dealer_code"],
        status=data["status"],
        signature_dealer_url=signature_dealer_url,
        signature_driver_url=signature_driver_url,
        created_at=_now_text(),
    )

    if data.get("return_info"):
        ret = data["return_info"]
        dealer_return = DealerReturn(
            confirmation=confirmation,
            driver=ret["driver"],
            return_date=ret["return_date"],
            notes=ret.get("notes", ""),
        )
        confirmation.return_record = dealer_return

    db.add(confirmation)

    pl = item.picking_list
    status_text = {
        "match": "sesuai",
        "shortage": "hutang",
        "excess": "lebih (retur)",
    }
    pl.history.append(HistoryEntry(
        at=_now_text(), by=user_name,
        text=f"Dealer {data['dealer_code']} konfirmasi barang {item.name} {status_text.get(data['status'], data['status'])}.",
    ))
    pl.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(confirmation)
    return confirmation


def get_list_totals(picking_list) -> dict:
    planned = sum(i.planned_qty for i in picking_list.items)
    actual = sum(i.actual_qty for i in picking_list.items)
    paid = sum(
        sum(s.qty for s in i.settlements)
        for i in picking_list.items
    )
    debt_active = picking_list.status in ("picked",) or bool(picking_list.handover)
    debt = max(planned - actual - paid, 0) if debt_active else 0
    confirmed = sum(1 for i in picking_list.items if i.confirmed)
    return {"planned": planned, "actual": actual, "paid": paid, "debt": debt, "confirmed": confirmed}
