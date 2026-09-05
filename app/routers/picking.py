from __future__ import annotations
import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user, require_admin_kepala
from app.models import User
from app.schemas.picking import DashboardStats, HandoverCreate
from app.services import picking_service

logger = logging.getLogger("picking.upload")

router = APIRouter(prefix="/api/picking", tags=["picking"])


def _serialize_picking_list(row):
    return {
        "id": row.id,
        "picking_id": row.picking_id,
        "date": row.date,
        "no_ds": row.no_ds,
        "expedition": row.expedition,
        "plate": row.plate,
        "driver": row.driver,
        "status": row.status,
        "source_file": row.source_file,
        "handover": {
            "admin_name": row.handover.admin_name,
            "driver_name": row.handover.driver_name,
            "signature_admin_url": row.handover.signature_admin_url,
            "signature_driver_url": row.handover.signature_driver_url,
            "created_by": row.handover.created_by,
            "created_at": row.handover.created_at,
        } if row.handover else None,
        "history": [
            {"at": item.at, "by": item.by, "text": item.text}
            for item in row.history
        ],
        "items": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "category": item.category,
                "planned_qty": item.planned_qty,
                "actual_qty": item.actual_qty,
                "confirmed": item.confirmed,
                "note": item.note,
                "dealers": [
                    {
                        "no_so": dealer.no_so,
                        "code": dealer.code,
                        "dealer": dealer.dealer_name,
                        "qty": dealer.qty,
                    }
                    for dealer in item.dealers
                ],
                "settlements": [
                    {
                        "qty": settlement.qty,
                        "date": settlement.date.isoformat(),
                        "driver": settlement.driver,
                        "note": settlement.note,
                        "by": settlement.by,
                        "at": settlement.at,
                    }
                    for settlement in item.settlements
                ],
                "dealer_confirmations": [
                    {
                        "id": confirmation.id,
                        "dealer_code": confirmation.dealer_code,
                        "status": confirmation.status,
                        "signature_dealer_url": confirmation.signature_dealer_url,
                        "signature_driver_url": confirmation.signature_driver_url,
                        "created_at": confirmation.created_at,
                        "return_record": {
                            "driver": confirmation.return_record.driver,
                            "return_date": confirmation.return_record.return_date.isoformat(),
                            "notes": confirmation.return_record.notes,
                        } if confirmation.return_record else None,
                    }
                    for confirmation in item.dealer_confirmations
                ],
            }
            for item in row.items
        ],
    }


@router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not (file.filename.endswith(".xlsx") or file.filename.endswith(".xls")):
        raise HTTPException(status_code=400, detail="File harus berformat .xlsx atau .xls.")
    content = await file.read()
    logger.info("Upload received: filename=%s, size=%d bytes", file.filename, len(content))
    if len(content) < 50:
        raise HTTPException(status_code=400, detail=f"File terlalu kecil ({len(content)} bytes).")
    suffix = ".xlsx" if file.filename.endswith(".xlsx") else ".xls"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(content)
        tmp.close()
        if suffix == ".xlsx":
            import zipfile
            if not zipfile.is_zipfile(tmp.name):
                with open(tmp.name, "rb") as f:
                    head = f.read(200)
                raise HTTPException(
                    status_code=400,
                    detail=f"File xlsx tidak valid. 200 byte pertama: {head[:80].hex()}",
                )
        result = await picking_service.import_excel(
            db, tmp.name, file.filename, user.name, user.id
        )
        return {
            "status": "ok",
            "imported_count": len(result),
            "lists": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@router.get("/dashboard")
async def dashboard(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    lists = await picking_service.get_picking_lists(
        db, user.role, user.expedition, user.dealer_code
    )
    total = len(lists)
    draft_count = sum(1 for l in lists if l.status == "draft")
    picked_count = sum(1 for l in lists if l.status in ("picked", "handover_completed"))
    handover_count = sum(1 for l in lists if l.handover)
    total_items = sum(sum(i.planned_qty for i in l.items) for l in lists)
    total_debt = sum(
        max(sum(i.planned_qty for i in l.items) - sum(i.actual_qty for i in l.items), 0)
        for l in lists if l.status in ("picked", "handover_completed") or l.handover
    )
    return DashboardStats(
        total_picking=total, draft_count=draft_count,
        picked_count=picked_count, handover_count=handover_count,
        total_items=total_items, total_debt=total_debt,
    )


@router.get("/")
async def list_picking(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    lists = await picking_service.get_picking_lists(
        db, user.role, user.expedition, user.dealer_code
    )
    return {"lists": [_serialize_picking_list(row) for row in lists]}


@router.get("/{list_id}")
async def get_detail(list_id: str, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    pl = await picking_service.get_picking_list(db, list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Picking list not found")
    return _serialize_picking_list(pl)


@router.put("/{list_id}/items")
async def update_items(
    list_id: str, items: list[dict],
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    pl = await picking_service.update_picking_items(
        db, list_id, items, user.name, user.id
    )
    if not pl:
        raise HTTPException(status_code=404, detail="Picking list not found")
    return _serialize_picking_list(pl)


@router.post("/{list_id}/complete")
async def complete_picking(
    list_id: str,
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    result = await picking_service.complete_picking(db, list_id, user.name, user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Picking list not found")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/{list_id}/handover")
async def create_handover(
    list_id: str,
    data: HandoverCreate,
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    handover = await picking_service.create_handover(
        db, list_id, data.model_dump(), user.name, user.id
    )
    if not handover:
        raise HTTPException(status_code=400, detail="Picking harus complete sebelum serah terima.")
    return handover


@router.get("/{list_id}/handover")
async def get_handover(
    list_id: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    pl = await picking_service.get_picking_list(db, list_id)
    if not pl or not pl.handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    return pl.handover
