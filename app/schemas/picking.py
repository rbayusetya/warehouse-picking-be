from __future__ import annotations
from pydantic import BaseModel


class DealerInfoOut(BaseModel):
    no_so: str | None = None
    code: str
    dealer: str
    qty: float

    class Config:
        from_attributes = True


class SettlementOut(BaseModel):
    qty: float
    date: str
    driver: str
    note: str
    by: str | None = None
    at: str

    class Config:
        from_attributes = True


class SettlementCreate(BaseModel):
    picking_item_id: str
    qty: float
    date: str
    driver: str
    note: str = ""


class DealerReturnOut(BaseModel):
    driver: str
    return_date: str
    notes: str

    class Config:
        from_attributes = True


class DealerConfirmationOut(BaseModel):
    id: str
    dealer_code: str
    status: str
    signature_dealer_url: str | None = None
    signature_driver_url: str | None = None
    created_at: str
    return_record: DealerReturnOut | None = None

    class Config:
        from_attributes = True


class PickingItemOut(BaseModel):
    id: str
    code: str
    name: str
    category: str
    planned_qty: float
    actual_qty: float
    confirmed: bool
    note: str
    dealers: list[DealerInfoOut] = []
    settlements: list[SettlementOut] = []
    dealer_confirmations: list[DealerConfirmationOut] = []

    class Config:
        from_attributes = True


class PickingItemUpdate(BaseModel):
    confirmed: bool | None = None
    actual_qty: float | None = None
    note: str | None = None


class HandoverOut(BaseModel):
    admin_name: str
    driver_name: str
    signature_admin_url: str | None = None
    signature_driver_url: str | None = None
    created_by: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class HistoryEntryOut(BaseModel):
    at: str
    by: str | None = None
    text: str

    class Config:
        from_attributes = True


class PickingListOut(BaseModel):
    id: str
    picking_id: str
    date: str
    no_ds: str | None = None
    expedition: str
    plate: str | None = None
    driver: str
    status: str
    source_file: str | None = None
    items: list[PickingItemOut] = []
    handover: HandoverOut | None = None
    history: list[HistoryEntryOut] = []

    class Config:
        from_attributes = True


class PickingListSummary(BaseModel):
    id: str
    picking_id: str
    date: str
    expedition: str
    driver: str
    plate: str | None = None
    status: str

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_picking: int
    draft_count: int
    picked_count: int
    handover_count: int
    total_items: int
    total_debt: float


class DebtItemOut(BaseModel):
    picking_list: PickingListSummary
    item: PickingItemOut
    paid: float
    debt: float


class HandoverCreate(BaseModel):
    admin_name: str
    driver_name: str
    signature_admin: str | None = None
    signature_driver: str | None = None


class SettlementHandoverCreate(BaseModel):
    settlement_id: str
    admin_name: str
    driver_name: str
    signature_admin: str | None = None
    signature_driver: str | None = None


class SettlementHandoverOut(BaseModel):
    id: str
    settlement_id: str
    admin_name: str
    driver_name: str
    signature_admin_url: str | None = None
    signature_driver_url: str | None = None
    created_by: str | None = None
    created_at: str

    class Config:
        from_attributes = True
