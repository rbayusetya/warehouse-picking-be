from __future__ import annotations
import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user, require_admin_kepala
from app.models import User
from app.schemas.picking import (
    PickingListOut, PickingListSummary, PickingItemUpdate,
    DashboardStats, DebtItemOut, HandoverCreate, HandoverOut,
)
from app.services import picking_service

logger = logging.getLogger("picking.upload")

router = APIRouter(prefix="/api/picking", tags=["picking"])


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
        result = await picking_service.import_excel(db, tmp.name, file.filename, user.name)
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
    picked_count = sum(1 for l in lists if l.status == "picked")
    handover_count = sum(1 for l in lists if l.handover)
    total_items = sum(sum(i.planned_qty for i in l.items) for l in lists)
    total_debt = sum(
        max(sum(i.planned_qty for i in l.items) - sum(i.actual_qty for i in l.items), 0)
        for l in lists if l.status in ("picked",) or l.handover
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
    result = []
    for l in lists:
        result.append({
            "id": l.id,
            "picking_id": l.picking_id,
            "date": l.date,
            "no_ds": l.no_ds,
            "expedition": l.expedition,
            "plate": l.plate,
            "driver": l.driver,
            "status": l.status,
            "source_file": l.source_file,
            "handover": {
                "admin_name": l.handover.admin_name,
                "driver_name": l.handover.driver_name,
                "signature_admin_url": l.handover.signature_admin_url,
                "signature_driver_url": l.handover.signature_driver_url,
                "created_by": l.handover.created_by,
                "created_at": l.handover.created_at,
            } if l.handover else None,
            "history": [{"at": h.at, "by": h.by, "text": h.text} for h in l.history],
            "items": [
                {
                    "id": i.id, "code": i.code, "name": i.name,
                    "category": i.category,
                    "planned_qty": i.planned_qty, "actual_qty": i.actual_qty,
                    "confirmed": i.confirmed, "note": i.note,
                    "dealers": [
                        {"no_so": d.no_so, "code": d.code,
                         "dealer": d.dealer, "qty": d.qty}
                        for d in i.dealers
                    ],
                    "settlements": [
                        {"qty": s.qty, "date": s.date, "driver": s.driver,
                         "note": s.note, "by": s.by, "at": s.at}
                        for s in i.settlements
                    ],
                    "dealer_confirmations": [
                        {
                            "id": dc.id, "dealer_code": dc.dealer_code,
                            "status": dc.status,
                            "signature_dealer_url": dc.signature_dealer_url,
                            "signature_driver_url": dc.signature_driver_url,
                            "created_at": dc.created_at,
                            "return_record": {
                                "driver": dc.return_record.driver,
                                "return_date": dc.return_record.return_date,
                                "notes": dc.return_record.notes,
                            } if dc.return_record else None,
                        }
                        for dc in i.dealer_confirmations
                    ],
                }
                for i in l.items
            ],
        })
    return {"lists": result}


@router.get("/{list_id}")
async def get_detail(list_id: str, user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    pl = await picking_service.get_picking_list(db, list_id)
    if not pl:
        raise HTTPException(status_code=404, detail="Picking list not found")
    return pl


@router.put("/{list_id}/items")
async def update_items(
    list_id: str, items: list[dict],
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    pl = await picking_service.update_picking_items(db, list_id, items, user.name)
    if not pl:
        raise HTTPException(status_code=404, detail="Picking list not found")
    return pl


@router.post("/{list_id}/complete")
async def complete_picking(
    list_id: str,
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    result = await picking_service.complete_picking(db, list_id, user.name)
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
        db, list_id, data.model_dump(), user.name
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
