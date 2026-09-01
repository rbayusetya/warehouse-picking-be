from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user, require_admin_kepala
from app.models import User
from app.schemas.picking import SettlementHandoverCreate, SettlementHandoverOut
from app.services import picking_service

router = APIRouter(prefix="/api/settlement-handovers", tags=["settlement-handovers"])


@router.get("/")
async def list_settlement_handovers(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await picking_service.list_settlement_handovers(db, user.role, user.expedition, user.dealer_code)
    return {
        "rows": [
            {
                "id": h.id,
                "settlement_id": h.settlement_id,
                "admin_name": h.admin_name,
                "driver_name": h.driver_name,
                "signature_admin_url": h.signature_admin_url,
                "signature_driver_url": h.signature_driver_url,
                "created_by": h.created_by,
                "created_at": h.created_at,
                "picking_list": {
                    "id": h.settlement.item.picking_list.id,
                    "picking_id": h.settlement.item.picking_list.picking_id,
                    "date": h.settlement.item.picking_list.date,
                    "driver": h.settlement.item.picking_list.driver,
                    "expedition": h.settlement.item.picking_list.expedition,
                },
                "item": {
                    "id": h.settlement.item.id,
                    "code": h.settlement.item.code,
                    "name": h.settlement.item.name,
                    "qty": h.settlement.qty,
                },
            }
            for h in rows
        ]
    }


@router.post("/")
async def create_settlement_handover(
    data: SettlementHandoverCreate,
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    handover = await picking_service.create_settlement_handover(
        db, data.settlement_id, data.model_dump(), user.name,
    )
    if not handover:
        raise HTTPException(status_code=400, detail="Settlement tidak ditemukan atau sudah di-handover.")
    return handover
