from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user
from app.models import User
from app.services import picking_service

router = APIRouter(prefix="/api/dealer", tags=["dealer"])


@router.get("/items")
async def get_dealer_items(user: User = Depends(require_user), db: AsyncSession = Depends(get_db)):
    if user.role != "dealer" or not user.dealer_code:
        raise HTTPException(status_code=403, detail="Akses hanya untuk dealer.")
    items = await picking_service.get_dealer_items(db, user.dealer_code)
    return {"items": items}


@router.get("/items/{picking_list_id}")
async def get_dealer_items_by_list(
    picking_list_id: str,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "dealer" or not user.dealer_code:
        raise HTTPException(status_code=403, detail="Akses hanya untuk dealer.")
    items = await picking_service.get_dealer_items(db, user.dealer_code)
    filtered = [i for i in items if i["picking_list_id"] == picking_list_id]
    return {"items": filtered, "list_id": picking_list_id}


@router.post("/confirm")
async def confirm_item(
    data: dict,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != "dealer" or not user.dealer_code:
        raise HTTPException(status_code=403, detail="Akses hanya untuk dealer.")
    data["dealer_code"] = user.dealer_code
    confirmation = await picking_service.create_dealer_confirmation(db, data, user.name)
    if not confirmation:
        raise HTTPException(status_code=404, detail="Item tidak ditemukan.")
    return {"status": "ok", "id": confirmation.id}
