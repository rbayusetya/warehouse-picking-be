from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Dealer,
    DealerConfirmation,
    DealerReturn,
    HistoryEntry,
    Handover,
    KSU,
    PickingItem,
    PickingItemDealer,
    PickingList,
    SalesOrder,
    SalesOrderItem,
    Settlement,
    SettlementHandover,
    Truck,
    UploadedFile,
)
from app.services import s3_service

from picking_excel import parse_picking_workbook


def _now_text() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _parse_date(value: str | date_type | datetime) -> date_type:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_type):
        return value
    text = str(value).strip()
    try:
        return date_type.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"Tanggal tidak valid: {value}") from exc


def _date_text(value: date_type | datetime | str | None) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_type):
        return value.isoformat()
    return str(value or "")


def _picking_options():
    return (
        selectinload(PickingList.truck),
        selectinload(PickingList.items).selectinload(PickingItem.ksu),
        selectinload(PickingList.items)
        .selectinload(PickingItem.dealers)
        .selectinload(PickingItemDealer.dealer),
        selectinload(PickingList.items)
        .selectinload(PickingItem.dealers)
        .selectinload(PickingItemDealer.sales_order),
        selectinload(PickingList.items).selectinload(PickingItem.settlements),
        selectinload(PickingList.items)
        .selectinload(PickingItem.dealer_confirmations)
        .selectinload(DealerConfirmation.dealer),
        selectinload(PickingList.items)
        .selectinload(PickingItem.dealer_confirmations)
        .selectinload(DealerConfirmation.return_record),
        selectinload(PickingList.handover),
        selectinload(PickingList.history),
    )


async def import_excel(
    db: AsyncSession,
    file_path: str,
    filename: str,
    uploaded_by: str,
    uploaded_by_id: str | None = None,
) -> list[dict]:
    parsed = parse_picking_workbook(file_path)

    dealers_by_code = {
        row.code: row for row in (await db.execute(select(Dealer))).scalars().all()
    }
    trucks_by_plate = {
        row.plate_number: row for row in (await db.execute(select(Truck))).scalars().all()
    }
    ksus_by_code = {
        row.code: row for row in (await db.execute(select(KSU))).scalars().all()
    }
    orders_by_number = {
        row.sales_order_number: row
        for row in (await db.execute(select(SalesOrder))).scalars().all()
    }
    order_items_by_key: dict[tuple[str, str, str], SalesOrderItem] = {}
    order_item_rows = await db.execute(
        select(SalesOrderItem)
        .options(
            selectinload(SalesOrderItem.sales_order),
            selectinload(SalesOrderItem.dealer),
            selectinload(SalesOrderItem.ksu),
        )
    )
    for row in order_item_rows.scalars().all():
        order_items_by_key[
            (row.sales_order.sales_order_number, row.dealer.code, row.ksu.code)
        ] = row

    db.add(
        UploadedFile(
            filename=filename,
            original_name=filename,
            uploaded_by_id=uploaded_by_id,
            uploaded_by=uploaded_by,
        )
    )

    for list_data in parsed:
        expedition = (list_data.get("expedition") or "").strip()
        plate = (list_data.get("plate") or "").strip()
        driver = (list_data.get("driver") or "").strip()
        if not expedition or not plate or not driver:
            raise ValueError(
                f"Data truck untuk No Picking List {list_data['id']} tidak lengkap."
            )

        truck = trucks_by_plate.get(plate)
        if truck is None:
            truck = Truck(
                expedition_name=expedition,
                plate_number=plate,
                driver_name=driver,
            )
            trucks_by_plate[plate] = truck
            db.add(truck)
        else:
            truck.expedition_name = expedition
            truck.driver_name = driver

        picking_list = PickingList(
            picking_number=list_data["id"],
            delivery_schedule_number=list_data.get("noDs", ""),
            date_time=_parse_date(list_data["date"]),
            truck=truck,
            created_by_id=uploaded_by_id,
            status="draft",
            source_file=filename,
        )
        picking_list.history.append(
            HistoryEntry(
                at=_now_text(),
                by=uploaded_by,
                user_id=uploaded_by_id,
                text=f"Data picking diimpor dari Excel. No Picking List {list_data['id']}.",
            )
        )

        for item_data in list_data["items"]:
            code = item_data["code"].strip()
            ksu = ksus_by_code.get(code)
            if ksu is None:
                ksu = KSU(
                    code=code,
                    type=item_data["category"],
                    name=item_data["name"],
                )
                ksus_by_code[code] = ksu
                db.add(ksu)
            else:
                ksu.type = item_data["category"]
                ksu.name = item_data["name"]

            item = PickingItem(
                picking_list=picking_list,
                ksu=ksu,
                planned_qty=item_data["plannedQty"],
                actual_qty=0,
                confirmed=False,
                note="",
            )

            for dealer_data in item_data.get("dealers", []):
                dealer_code = (dealer_data.get("code") or "").strip()
                dealer_name = (dealer_data.get("dealer") or "").strip()
                no_so = (dealer_data.get("noSo") or "").strip()
                if not dealer_code or not dealer_name:
                    raise ValueError(
                        f"Dealer untuk KSU {code} pada No Picking List "
                        f"{list_data['id']} tidak lengkap."
                    )

                dealer = dealers_by_code.get(dealer_code)
                if dealer is None:
                    dealer = Dealer(code=dealer_code, name=dealer_name)
                    dealers_by_code[dealer_code] = dealer
                    db.add(dealer)
                elif dealer.name != dealer_name:
                    dealer.name = dealer_name

                sales_order = None
                sales_order_item = None
                if no_so:
                    sales_order = orders_by_number.get(no_so)
                    if sales_order is None:
                        sales_order = SalesOrder(sales_order_number=no_so)
                        orders_by_number[no_so] = sales_order
                        db.add(sales_order)
                    if dealer not in sales_order.dealers:
                        sales_order.dealers.append(dealer)
                    if sales_order not in picking_list.sales_orders:
                        picking_list.sales_orders.append(sales_order)

                    key = (no_so, dealer_code, code)
                    sales_order_item = order_items_by_key.get(key)
                    if sales_order_item is None:
                        sales_order_item = SalesOrderItem(
                            sales_order=sales_order,
                            dealer=dealer,
                            ksu=ksu,
                            ordered_qty=dealer_data["qty"],
                        )
                        order_items_by_key[key] = sales_order_item
                        db.add(sales_order_item)
                    else:
                        sales_order_item.ordered_qty += dealer_data["qty"]

                item.dealers.append(
                    PickingItemDealer(
                        item=item,
                        sales_order=sales_order,
                        sales_order_item=sales_order_item,
                        dealer=dealer,
                        qty=dealer_data["qty"],
                    )
                )
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
    stmt = (
        select(PickingList)
        .options(*_picking_options())
        .order_by(PickingList.created_at.desc())
    )
    if user_role == "ekspedisi" and user_expedition:
        stmt = stmt.join(PickingList.truck).where(
            Truck.expedition_name == user_expedition
        )
    elif user_role == "dealer" and user_dealer_code:
        stmt = stmt.where(
            PickingList.items.any(
                PickingItem.dealers.any(
                    PickingItemDealer.dealer.has(Dealer.code == user_dealer_code)
                )
            )
        )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_picking_list(db: AsyncSession, list_id: str) -> PickingList | None:
    stmt = (
        select(PickingList)
        .options(*_picking_options())
        .where(PickingList.picking_number == list_id)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_picking_items(
    db: AsyncSession,
    list_id: str,
    items_data: list[dict],
    user_name: str,
    user_id: str | None = None,
) -> PickingList | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list:
        return None
    for update in items_data:
        item = next(
            (row for row in picking_list.items if row.id == update.get("id")),
            None,
        )
        if not item:
            continue
        if "confirmed" in update:
            item.confirmed = bool(update["confirmed"])
        if "actual_qty" in update:
            previous = item.actual_qty
            item.actual_qty = float(update["actual_qty"])
            if picking_list.status == "picked" and previous != item.actual_qty:
                picking_list.history.append(
                    HistoryEntry(
                        at=_now_text(),
                        by=user_name,
                        user_id=user_id,
                        text=f"Revisi aktual {item.name}: {previous} menjadi {item.actual_qty}.",
                    )
                )
        if "note" in update:
            previous_note = item.note
            item.note = update["note"] or ""
            if picking_list.status == "picked" and previous_note != item.note:
                picking_list.history.append(
                    HistoryEntry(
                        at=_now_text(),
                        by=user_name,
                        user_id=user_id,
                        text=f"Revisi notes {item.name}.",
                    )
                )
    picking_list.updated_at = datetime.utcnow()
    await db.commit()
    return await get_picking_list(db, list_id)


async def complete_picking(
    db: AsyncSession,
    list_id: str,
    user_name: str,
    user_id: str | None = None,
) -> dict | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list:
        return None
    unconfirmed = [item for item in picking_list.items if not item.confirmed]
    if unconfirmed:
        return {"error": f"Masih ada {len(unconfirmed)} item belum dicentang."}
    missing_notes = [
        item.name
        for item in picking_list.items
        if item.actual_qty < item.planned_qty and not item.note.strip()
    ]
    if missing_notes:
        return {"error": "Notes wajib untuk: " + ", ".join(missing_notes[:5])}

    picking_list.status = "picked"
    planned = sum(item.planned_qty for item in picking_list.items)
    actual = sum(item.actual_qty for item in picking_list.items)
    debt = max(planned - actual, 0)
    text = f"Picking selesai dengan hutang {debt} qty." if debt else "Picking selesai lengkap."
    picking_list.history.append(
        HistoryEntry(at=_now_text(), by=user_name, user_id=user_id, text=text)
    )
    picking_list.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "ok", "debt": debt}


async def create_handover(
    db: AsyncSession,
    list_id: str,
    data: dict,
    user_name: str,
    user_id: str | None = None,
) -> Handover | None:
    picking_list = await get_picking_list(db, list_id)
    if not picking_list or picking_list.status != "picked":
        return None

    signature_admin_url = None
    signature_driver_url = None
    if data.get("signature_admin"):
        signature_admin_url = s3_service.upload_base64_to_s3(
            data["signature_admin"],
            f"signatures/{picking_list.id}_admin_{_now_text().replace('/', '-')}.png",
            "image/png",
        )
    if data.get("signature_driver"):
        signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"],
            f"signatures/{picking_list.id}_driver_{_now_text().replace('/', '-')}.png",
            "image/png",
        )

    handover = Handover(
        picking_list_id=picking_list.id,
        admin_name=data["admin_name"],
        driver_name=data["driver_name"],
        signature_admin_url=signature_admin_url,
        signature_driver_url=signature_driver_url,
        created_by_id=user_id,
        created_by=user_name,
        created_at=_now_text(),
    )
    db.add(handover)

    planned = sum(item.planned_qty for item in picking_list.items)
    actual = sum(item.actual_qty for item in picking_list.items)
    paid = sum(
        sum(settlement.qty for settlement in item.settlements)
        for item in picking_list.items
    )
    debt = max(planned - actual - paid, 0)
    text = f"Serah terima selesai dengan hutang {debt} qty." if debt else "Serah terima selesai lengkap."
    picking_list.history.append(
        HistoryEntry(at=_now_text(), by=user_name, user_id=user_id, text=text)
    )
    picking_list.updated_at = datetime.utcnow()
    picking_list.status = "handover_completed"
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
    for picking_list in lists:
        for item in picking_list.items:
            paid = sum(settlement.qty for settlement in item.settlements)
            debt_active = picking_list.status in ("picked", "handover_completed") or bool(
                picking_list.handover
            )
            if not debt_active:
                continue
            debt = max(item.planned_qty - item.actual_qty - paid, 0)
            if paid > 0 or debt > 0:
                results.append(
                    {
                        "picking_list": picking_list,
                        "item": item,
                        "paid": paid,
                        "debt": debt,
                    }
                )
    return results


async def create_settlement(
    db: AsyncSession,
    picking_item_id: str,
    qty: float,
    settlement_date: str,
    driver: str,
    note: str,
    user_name: str,
    user_id: str | None = None,
) -> Settlement | None:
    stmt = (
        select(PickingItem)
        .options(
            selectinload(PickingItem.picking_list).selectinload(PickingList.history),
            selectinload(PickingItem.settlements),
            selectinload(PickingItem.ksu),
        )
        .where(PickingItem.id == picking_item_id)
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        return None

    remaining = max(
        item.planned_qty
        - item.actual_qty
        - sum(settlement.qty for settlement in item.settlements),
        0,
    )
    if qty <= 0 or qty > remaining:
        raise ValueError(f"Jumlah pembayaran harus lebih dari 0 dan maksimal {remaining}.")

    settlement = Settlement(
        picking_item_id=picking_item_id,
        qty=qty,
        date=_parse_date(settlement_date),
        driver=driver,
        note=note,
        by=user_name,
        created_by_id=user_id,
        at=_now_text(),
    )
    db.add(settlement)
    item.picking_list.history.append(
        HistoryEntry(
            at=_now_text(),
            by=user_name,
            user_id=user_id,
            text=f"Pembayaran hutang {item.name} sebanyak {qty} qty dibawa {driver}.",
        )
    )
    item.picking_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(settlement)
    return settlement


async def create_settlement_handover(
    db: AsyncSession,
    settlement_id: str,
    data: dict,
    user_name: str,
    user_id: str | None = None,
) -> SettlementHandover | None:
    stmt = (
        select(Settlement)
        .options(
            selectinload(Settlement.handover),
            selectinload(Settlement.item)
            .selectinload(PickingItem.picking_list)
            .selectinload(PickingList.history),
            selectinload(Settlement.item).selectinload(PickingItem.ksu),
        )
        .where(Settlement.id == settlement_id)
    )
    settlement = (await db.execute(stmt)).scalar_one_or_none()
    if not settlement or settlement.handover:
        return None

    signature_admin_url = None
    signature_driver_url = None
    if data.get("signature_admin"):
        signature_admin_url = s3_service.upload_base64_to_s3(
            data["signature_admin"],
            f"settlement-signatures/{settlement_id}_admin_{_now_text().replace('/', '-')}.png",
            "image/png",
        )
    if data.get("signature_driver"):
        signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"],
            f"settlement-signatures/{settlement_id}_driver_{_now_text().replace('/', '-')}.png",
            "image/png",
        )

    handover = SettlementHandover(
        settlement_id=settlement_id,
        admin_name=data["admin_name"],
        driver_name=data["driver_name"],
        signature_admin_url=signature_admin_url,
        signature_driver_url=signature_driver_url,
        created_by_id=user_id,
        created_by=user_name,
        created_at=_now_text(),
    )
    db.add(handover)

    picking_list = settlement.item.picking_list
    picking_list.history.append(
        HistoryEntry(
            at=_now_text(),
            by=user_name,
            user_id=user_id,
            text=(
                f"Serah terima pembayaran hutang {settlement.item.name} "
                f"{settlement.qty} qty oleh admin {data['admin_name']}, "
                f"driver {data['driver_name']}."
            ),
        )
    )
    picking_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(handover)
    return handover


async def list_settlement_handovers(
    db: AsyncSession,
    user_role: str,
    user_expedition: str | None,
    user_dealer_code: str | None,
) -> list[SettlementHandover]:
    stmt = (
        select(SettlementHandover)
        .options(
            selectinload(SettlementHandover.settlement)
            .selectinload(Settlement.item)
            .selectinload(PickingItem.picking_list)
            .selectinload(PickingList.truck),
            selectinload(SettlementHandover.settlement)
            .selectinload(Settlement.item)
            .selectinload(PickingItem.ksu),
        )
        .order_by(SettlementHandover.created_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().unique().all())
    if user_role == "ekspedisi" and user_expedition:
        rows = [
            row
            for row in rows
            if row.settlement.item.picking_list.expedition == user_expedition
        ]
    return rows


async def get_dealer_items(db: AsyncSession, dealer_code: str) -> list[dict]:
    stmt = (
        select(PickingItem)
        .options(
            selectinload(PickingItem.picking_list).selectinload(PickingList.truck),
            selectinload(PickingItem.dealers).selectinload(PickingItemDealer.dealer),
            selectinload(PickingItem.dealers).selectinload(PickingItemDealer.sales_order),
            selectinload(PickingItem.settlements),
            selectinload(PickingItem.ksu),
            selectinload(PickingItem.dealer_confirmations)
            .selectinload(DealerConfirmation.dealer),
            selectinload(PickingItem.dealer_confirmations)
            .selectinload(DealerConfirmation.return_record),
        )
        .join(PickingItemDealer)
        .join(Dealer)
        .where(Dealer.code == dealer_code)
    )
    items = list((await db.execute(stmt)).scalars().unique().all())

    output = []
    for item in items:
        picking_list = item.picking_list
        dealer_info = next(
            (row for row in item.dealers if row.code == dealer_code),
            None,
        )
        if not dealer_info:
            continue
        confirmation = next(
            (row for row in item.dealer_confirmations if row.dealer_code == dealer_code),
            None,
        )
        output.append(
            {
                "picking_list_id": picking_list.id,
                "picking_id": picking_list.picking_id,
                "date": picking_list.date,
                "driver": picking_list.driver,
                "expedition": picking_list.expedition,
                "item_id": item.id,
                "item_name": item.name,
                "item_code": item.code,
                "item_category": item.category,
                "planned_qty": item.planned_qty,
                "actual_qty": item.actual_qty,
                "note": item.note,
                "dealer_code": dealer_code,
                "dealer_name": dealer_info.dealer_name,
                "dealer_qty": dealer_info.qty,
                "confirmation_status": confirmation.status if confirmation else None,
                "settlements": [
                    {
                        "qty": row.qty,
                        "date": _date_text(row.date),
                        "driver": row.driver,
                        "note": row.note,
                        "by": row.by,
                    }
                    for row in item.settlements
                ],
            }
        )
    return output


async def create_dealer_confirmation(
    db: AsyncSession,
    data: dict,
    user_name: str,
    user_id: str | None = None,
) -> DealerConfirmation | None:
    stmt = (
        select(PickingItem)
        .options(
            selectinload(PickingItem.picking_list).selectinload(PickingList.history),
            selectinload(PickingItem.ksu),
            selectinload(PickingItem.dealers).selectinload(PickingItemDealer.dealer),
            selectinload(PickingItem.dealer_confirmations),
        )
        .where(PickingItem.id == data["picking_item_id"])
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        return None

    dealer_info = next(
        (row for row in item.dealers if row.code == data["dealer_code"]),
        None,
    )
    if not dealer_info:
        return None

    existing = next(
        (row for row in item.dealer_confirmations if row.dealer_code == data["dealer_code"]),
        None,
    )
    if existing:
        confirmation = existing
        confirmation.status = data["status"]
    else:
        confirmation = DealerConfirmation(
            picking_item_id=data["picking_item_id"],
            dealer_id=dealer_info.dealer_id,
            status=data["status"],
            created_at=_now_text(),
        )
        db.add(confirmation)

    if data.get("signature_dealer"):
        confirmation.signature_dealer_url = s3_service.upload_base64_to_s3(
            data["signature_dealer"],
            f"dealer_sig/{data['picking_item_id']}_{data['dealer_code']}_dealer.png",
        )
    if data.get("signature_driver"):
        confirmation.signature_driver_url = s3_service.upload_base64_to_s3(
            data["signature_driver"],
            f"dealer_sig/{data['picking_item_id']}_{data['dealer_code']}_driver.png",
        )

    if data.get("return_info"):
        ret = data["return_info"]
        if confirmation.return_record:
            confirmation.return_record.driver = ret["driver"]
            confirmation.return_record.return_date = _parse_date(ret["return_date"])
            confirmation.return_record.notes = ret.get("notes", "")
        else:
            confirmation.return_record = DealerReturn(
                driver=ret["driver"],
                return_date=_parse_date(ret["return_date"]),
                notes=ret.get("notes", ""),
            )

    status_text = {
        "match": "sesuai",
        "shortage": "hutang",
        "excess": "lebih (retur)",
    }
    item.picking_list.history.append(
        HistoryEntry(
            at=_now_text(),
            by=user_name,
            user_id=user_id,
            text=(
                f"Dealer {data['dealer_code']} konfirmasi barang {item.name} "
                f"{status_text.get(data['status'], data['status'])}."
            ),
        )
    )
    item.picking_list.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(confirmation)
    return confirmation


def get_list_totals(picking_list) -> dict:
    planned = sum(item.planned_qty for item in picking_list.items)
    actual = sum(item.actual_qty for item in picking_list.items)
    paid = sum(
        sum(settlement.qty for settlement in item.settlements)
        for item in picking_list.items
    )
    debt_active = picking_list.status in ("picked", "handover_completed") or bool(
        picking_list.handover
    )
    debt = max(planned - actual - paid, 0) if debt_active else 0
    confirmed = sum(1 for item in picking_list.items if item.confirmed)
    return {
        "planned": planned,
        "actual": actual,
        "paid": paid,
        "debt": debt,
        "confirmed": confirmed,
    }
