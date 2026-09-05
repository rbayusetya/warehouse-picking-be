from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user, require_admin_kepala
from app.models import User
from app.services import picking_service

router = APIRouter(prefix="/api/debts", tags=["debts"])


@router.get("/")
async def list_debts(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    rows = await picking_service.list_debts(db, user.role, user.expedition, user.dealer_code)
    result = []
    for row in rows:
        pl = row["picking_list"]
        item = row["item"]
        result.append({
            "picking_list": {
                "id": pl.id,
                "picking_id": pl.picking_id,
                "date": pl.date,
                "driver": pl.driver,
                "expedition": pl.expedition,
            },
            "item": {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "planned_qty": item.planned_qty,
                "actual_qty": item.actual_qty,
                "note": item.note,
            },
            "paid": row["paid"],
            "debt": row["debt"],
        })
    return {"rows": result}


@router.post("/pay")
async def pay_debt(
    data: dict,
    user: User = Depends(require_admin_kepala),
    db: AsyncSession = Depends(get_db),
):
    qty = float(data.get("qty", 0))
    settlement = await picking_service.create_settlement(
        db, data["picking_item_id"], qty,
        data.get("date", ""), data.get("driver", ""),
        data.get("note", ""), user.name, user.id,
    )
    if not settlement:
        raise HTTPException(status_code=404, detail="Item not found")
    return {
        "status": "ok",
        "settlement": {
            "id": settlement.id,
            "qty": settlement.qty,
            "date": settlement.date.isoformat(),
            "driver": settlement.driver,
        },
    }
