from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


sales_order_dealers = Table(
    "sales_order_dealers",
    Base.metadata,
    Column("sales_order_id", String(36), ForeignKey("sales_orders.id"), primary_key=True),
    Column("dealer_id", String(36), ForeignKey("dealers.id"), primary_key=True),
)

picking_list_sales_orders = Table(
    "picking_list_sales_orders",
    Base.metadata,
    Column("picking_list_id", String(36), ForeignKey("picking_lists.id"), primary_key=True),
    Column("sales_order_id", String(36), ForeignKey("sales_orders.id"), primary_key=True),
)


class Dealer(Base):
    __tablename__ = "dealers"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    users = relationship("User", back_populates="dealer")
    picking_allocations = relationship("PickingItemDealer", back_populates="dealer")
    confirmations = relationship("DealerConfirmation", back_populates="dealer")
    sales_orders = relationship(
        "SalesOrder",
        secondary=sales_order_dealers,
        back_populates="dealers",
    )


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition_name = Column(String(100), nullable=False)
    plate_number = Column(String(50), nullable=False, unique=True, index=True)
    driver_name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    picking_lists = relationship("PickingList", back_populates="truck")


class KSU(Base):
    __tablename__ = "ksus"

    code = Column(String(100), primary_key=True)
    type = Column(String(100), nullable=False)
    name = Column(String(300), nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    picking_items = relationship("PickingItem", back_populates="ksu")
    sales_order_items = relationship("SalesOrderItem", back_populates="ksu")


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(String(36), primary_key=True, default=_uuid)
    sales_order_number = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=_now, nullable=False)

    dealers = relationship(
        "Dealer",
        secondary=sales_order_dealers,
        back_populates="sales_orders",
    )
    items = relationship(
        "SalesOrderItem",
        back_populates="sales_order",
        cascade="all, delete-orphan",
    )
    picking_allocations = relationship("PickingItemDealer", back_populates="sales_order")
    picking_lists = relationship(
        "PickingList",
        secondary=picking_list_sales_orders,
        back_populates="sales_orders",
    )


class SalesOrderItem(Base):
    """Normalized sales-order line, including its dealer allocation."""

    __tablename__ = "sales_order_items"
    __table_args__ = (
        UniqueConstraint(
            "sales_order_id",
            "dealer_id",
            "ksu_code",
            name="uq_sales_order_item_dealer_ksu",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    sales_order_id = Column(String(36), ForeignKey("sales_orders.id"), nullable=False, index=True)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False, index=True)
    ksu_code = Column(String(100), ForeignKey("ksus.code"), nullable=False, index=True)
    ordered_qty = Column(Float, nullable=False, default=0)

    sales_order = relationship("SalesOrder", back_populates="items")
    dealer = relationship("Dealer")
    ksu = relationship("KSU", back_populates="sales_order_items")
    picking_allocations = relationship("PickingItemDealer", back_populates="sales_order_item")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=False, unique=True)
    role = Column(String(20), nullable=False)  # admin, kepala, ekspedisi, dealer
    role_label = Column(String(100), nullable=False)
    expedition = Column(String(100), nullable=True)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    dealer = relationship("Dealer", back_populates="users", lazy="joined")
    created_picking_lists = relationship(
        "PickingList",
        back_populates="created_by_user",
        foreign_keys="PickingList.created_by_id",
    )
    history_entries = relationship("HistoryEntry", back_populates="user")

    @property
    def dealer_code(self) -> str | None:
        return self.dealer.code if self.dealer else None


class PickingList(Base):
    __tablename__ = "picking_lists"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_number = Column(String(100), nullable=False, unique=True, index=True)
    delivery_schedule_number = Column(String(100), nullable=True)
    date_time = Column(Date, nullable=False)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False, index=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(30), default="draft", nullable=False)
    source_file = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    truck = relationship("Truck", back_populates="picking_lists")
    created_by_user = relationship(
        "User",
        back_populates="created_picking_lists",
        foreign_keys=[created_by_id],
    )
    sales_orders = relationship(
        "SalesOrder",
        secondary=picking_list_sales_orders,
        back_populates="picking_lists",
    )
    items = relationship(
        "PickingItem",
        back_populates="picking_list",
        cascade="all, delete-orphan",
        order_by="PickingItem.ksu_code",
    )
    handover = relationship(
        "Handover",
        back_populates="picking_list",
        uselist=False,
        cascade="all, delete-orphan",
    )
    history = relationship(
        "HistoryEntry",
        back_populates="picking_list",
        cascade="all, delete-orphan",
        order_by="HistoryEntry.at",
    )

    @property
    def picking_id(self) -> str:
        return self.picking_number

    @property
    def no_ds(self) -> str:
        return self.delivery_schedule_number or ""

    @property
    def date(self) -> str:
        return self.date_time.isoformat()

    @property
    def expedition(self) -> str:
        return self.truck.expedition_name if self.truck else ""

    @property
    def plate(self) -> str:
        return self.truck.plate_number if self.truck else ""

    @property
    def driver(self) -> str:
        return self.truck.driver_name if self.truck else ""


class PickingItem(Base):
    __tablename__ = "picking_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, index=True)
    ksu_code = Column(String(100), ForeignKey("ksus.code"), nullable=False, index=True)
    planned_qty = Column(Float, default=0, nullable=False)
    actual_qty = Column(Float, default=0, nullable=False)
    confirmed = Column(Boolean, default=False, nullable=False)
    note = Column(Text, default="", nullable=False)

    picking_list = relationship("PickingList", back_populates="items")
    ksu = relationship("KSU", back_populates="picking_items", lazy="joined")
    dealers = relationship(
        "PickingItemDealer",
        back_populates="item",
        cascade="all, delete-orphan",
    )
    settlements = relationship(
        "Settlement",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="Settlement.at",
    )
    dealer_confirmations = relationship(
        "DealerConfirmation",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    @property
    def code(self) -> str:
        return self.ksu.code if self.ksu else self.ksu_code

    @property
    def name(self) -> str:
        return self.ksu.name if self.ksu else ""

    @property
    def category(self) -> str:
        return self.ksu.type if self.ksu else ""


class PickingItemDealer(Base):
    __tablename__ = "picking_item_dealers"
    __table_args__ = (
        UniqueConstraint(
            "picking_item_id",
            "dealer_id",
            "sales_order_id",
            name="uq_picking_item_dealer_sales_order",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    sales_order_id = Column(String(36), ForeignKey("sales_orders.id"), nullable=True, index=True)
    sales_order_item_id = Column(
        String(36),
        ForeignKey("sales_order_items.id"),
        nullable=True,
        index=True,
    )
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False, index=True)
    qty = Column(Float, default=0, nullable=False)

    item = relationship("PickingItem", back_populates="dealers")
    sales_order = relationship("SalesOrder", back_populates="picking_allocations")
    dealer = relationship("Dealer", back_populates="picking_allocations")
    sales_order_item = relationship("SalesOrderItem", back_populates="picking_allocations")

    @property
    def no_so(self) -> str:
        return self.sales_order.sales_order_number if self.sales_order else ""

    @property
    def code(self) -> str:
        return self.dealer.code if self.dealer else ""

    @property
    def dealer_name(self) -> str:
        return self.dealer.name if self.dealer else ""

    @property
    def dealer_text(self) -> str:
        return self.dealer_name


class Handover(Base):
    __tablename__ = "handovers"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, unique=True)
    admin_name = Column(String(200), nullable=False)
    driver_name = Column(String(200), nullable=False)
    signature_admin_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(String(30), nullable=False)

    picking_list = relationship("PickingList", back_populates="handover")
    created_by_user = relationship("User", foreign_keys=[created_by_id])


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    qty = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    driver = Column(String(200), nullable=False)
    note = Column(Text, default="", nullable=False)
    by = Column(String(200), nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    at = Column(String(30), nullable=False)

    item = relationship("PickingItem", back_populates="settlements")
    handover = relationship(
        "SettlementHandover",
        back_populates="settlement",
        uselist=False,
        cascade="all, delete-orphan",
    )
    created_by_user = relationship("User", foreign_keys=[created_by_id])


class SettlementHandover(Base):
    __tablename__ = "settlement_handovers"

    id = Column(String(36), primary_key=True, default=_uuid)
    settlement_id = Column(String(36), ForeignKey("settlements.id"), nullable=False, unique=True)
    admin_name = Column(String(200), nullable=False)
    driver_name = Column(String(200), nullable=False)
    signature_admin_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(String(30), nullable=False)

    settlement = relationship("Settlement", back_populates="handover")
    created_by_user = relationship("User", foreign_keys=[created_by_id])


class DealerConfirmation(Base):
    __tablename__ = "dealer_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "picking_item_id",
            "dealer_id",
            name="uq_dealer_confirmation_item_dealer",
        ),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    signature_dealer_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False)

    item = relationship("PickingItem", back_populates="dealer_confirmations")
    dealer = relationship("Dealer", back_populates="confirmations")
    return_record = relationship(
        "DealerReturn",
        back_populates="confirmation",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def dealer_code(self) -> str:
        return self.dealer.code if self.dealer else ""


class DealerReturn(Base):
    __tablename__ = "dealer_returns"

    id = Column(String(36), primary_key=True, default=_uuid)
    dealer_confirmation_id = Column(String(36), ForeignKey("dealer_confirmations.id"), nullable=False, unique=True)
    driver = Column(String(200), nullable=False)
    return_date = Column(Date, nullable=False)
    notes = Column(Text, default="", nullable=False)
    signature_dealer_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)

    confirmation = relationship("DealerConfirmation", back_populates="return_record")


class HistoryEntry(Base):
    __tablename__ = "history_entries"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    at = Column(String(30), nullable=False)
    by = Column(String(200), nullable=True)
    text = Column(Text, nullable=False)

    picking_list = relationship("PickingList", back_populates="history")
    user = relationship("User", back_populates="history_entries")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=True)
    uploaded_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_by = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)
