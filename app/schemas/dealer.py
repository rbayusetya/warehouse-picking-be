from __future__ import annotations
from pydantic import BaseModel


class DealerConfirmationCreate(BaseModel):
    picking_item_id: str
    dealer_code: str
    status: str  # match, shortage, excess
    signature_dealer: str | None = None
    signature_driver: str | None = None


class DealerReturnCreate(BaseModel):
    dealer_confirmation_id: str
    driver: str
    return_date: str
    notes: str = ""
    signature_dealer: str | None = None
    signature_driver: str | None = None


class DealerItemOut(BaseModel):
    picking_list_id: str
    picking_id: str
    date: str
    driver: str
    expedition: str
    item_id: str
    item_name: str
    item_code: str
    item_category: str
    planned_qty: float
    actual_qty: float
    note: str
    dealer_code: str
    dealer_name: str
    dealer_qty: float
    confirmation_status: str | None = None
