from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, Float, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.utcnow()


# ─── Master Tables ───


class Truck(Base):
    __tablename__ = "trucks"

    id = Column(String(36), primary_key=True, default=_uuid)
    expedition = Column(String(100), nullable=False)
    plate = Column(String(50), nullable=False)
    driver_name = Column(String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint("expedition", "plate", "driver_name", name="uq_truck"),
    )

    picking_lists = relationship("PickingList", back_populates="truck")


class KsuItem(Base):
    __tablename__ = "ksu_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(100), nullable=False, unique=True)
    name = Column(String(300), nullable=False)
    category = Column(String(100), nullable=False)

    picking_items = relationship("PickingItem", back_populates="ksu_item")
    sales_orders = relationship("SalesOrder", back_populates="ksu_item")


class Dealer(Base):
    __tablename__ = "dealers"

    id = Column(String(36), primary_key=True, default=_uuid)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(300), nullable=False)

    picking_item_dealers = relationship("PickingItemDealer", back_populates="dealer")
    sales_orders = relationship("SalesOrder", back_populates="dealer")


class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(String(36), primary_key=True, default=_uuid)
    so_number = Column(String(100), nullable=False, unique=True)
    ksu_item_id = Column(String(36), ForeignKey("ksu_items.id"), nullable=False)
    ksu_quantity = Column(Float, nullable=False)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)

    ksu_item = relationship("KsuItem", back_populates="sales_orders")
    dealer = relationship("Dealer", back_populates="sales_orders")


# ─── Auth ───


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)  # admin, kepala, ekspedisi, dealer
    role_label = Column(String(100), nullable=False)
    expedition = Column(String(100), nullable=True)
    dealer_code = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)


# ─── Transaction Tables ───


class PickingList(Base):
    __tablename__ = "picking_lists"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_id = Column(String(100), nullable=False, index=True, unique=True)
    date = Column(String(20), nullable=False)
    no_ds = Column(String(100), nullable=True)
    truck_id = Column(String(36), ForeignKey("trucks.id"), nullable=False)
    status = Column(String(30), default="draft")  # draft, picked, handover_completed, closed
    source_file = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    truck = relationship("Truck", back_populates="picking_lists")
    items = relationship("PickingItem", back_populates="picking_list", cascade="all, delete-orphan",
                         order_by="PickingItem.category, PickingItem.name")
    handover = relationship("Handover", back_populates="picking_list", uselist=False, cascade="all, delete-orphan")
    history = relationship("HistoryEntry", back_populates="picking_list", cascade="all, delete-orphan",
                           order_by="HistoryEntry.at")


class PickingItem(Base):
    __tablename__ = "picking_items"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, index=True)
    ksu_item_id = Column(String(36), ForeignKey("ksu_items.id"), nullable=False)
    # Snapshot columns from ksu_items at import time (for fast reads without joins)
    code = Column(String(100), nullable=False)
    name = Column(String(300), nullable=False)
    category = Column(String(100), nullable=False)
    planned_qty = Column(Float, default=0)
    actual_qty = Column(Float, default=0)
    confirmed = Column(Boolean, default=False)
    note = Column(Text, default="")

    picking_list = relationship("PickingList", back_populates="items")
    ksu_item = relationship("KsuItem", back_populates="picking_items")
    dealers = relationship("PickingItemDealer", back_populates="item", cascade="all, delete-orphan")
    settlements = relationship("Settlement", back_populates="item", cascade="all, delete-orphan",
                                order_by="Settlement.at")
    dealer_confirmations = relationship("DealerConfirmation", back_populates="item", cascade="all, delete-orphan")


class PickingItemDealer(Base):
    __tablename__ = "picking_item_dealers"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    dealer_id = Column(String(36), ForeignKey("dealers.id"), nullable=False)
    no_so = Column(String(100), nullable=True)
    qty = Column(Float, default=0)

    item = relationship("PickingItem", back_populates="dealers")
    dealer = relationship("Dealer", back_populates="picking_item_dealers")


# ─── Operational Tables ───


class Handover(Base):
    __tablename__ = "handovers"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, unique=True)
    admin_name = Column(String(200), nullable=False)
    driver_name = Column(String(200), nullable=False)
    signature_admin_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(String(30), nullable=False)

    picking_list = relationship("PickingList", back_populates="handover")


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    qty = Column(Float, nullable=False)
    date = Column(String(20), nullable=False)
    driver = Column(String(200), nullable=False)
    note = Column(Text, default="")
    by = Column(String(200), nullable=True)
    at = Column(String(30), nullable=False)

    item = relationship("PickingItem", back_populates="settlements")
    handover = relationship("SettlementHandover", back_populates="settlement", uselist=False, cascade="all, delete-orphan")


class SettlementHandover(Base):
    __tablename__ = "settlement_handovers"

    id = Column(String(36), primary_key=True, default=_uuid)
    settlement_id = Column(String(36), ForeignKey("settlements.id"), nullable=False, unique=True)
    admin_name = Column(String(200), nullable=False)
    driver_name = Column(String(200), nullable=False)
    signature_admin_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(String(30), nullable=False)

    settlement = relationship("Settlement", back_populates="handover")


class DealerConfirmation(Base):
    __tablename__ = "dealer_confirmations"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_item_id = Column(String(36), ForeignKey("picking_items.id"), nullable=False, index=True)
    dealer_code = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # match, shortage, excess
    signature_dealer_url = Column(Text, nullable=True)
    signature_driver_url = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False)

    item = relationship("PickingItem", back_populates="dealer_confirmations")
    return_record = relationship("DealerReturn", back_populates="confirmation", uselist=False,
                                  cascade="all, delete-orphan")


class DealerReturn(Base):
    __tablename__ = "dealer_returns"

    id = Column(String(36), primary_key=True, default=_uuid)
    dealer_confirmation_id = Column(String(36), ForeignKey("dealer_confirmations.id"), nullable=False, unique=True)
    driver = Column(String(200), nullable=False)
    return_date = Column(String(20), nullable=False)
    notes = Column(Text, default="")

    confirmation = relationship("DealerConfirmation", back_populates="return_record")


class HistoryEntry(Base):
    __tablename__ = "history_entries"

    id = Column(String(36), primary_key=True, default=_uuid)
    picking_list_id = Column(String(36), ForeignKey("picking_lists.id"), nullable=False, index=True)
    at = Column(String(30), nullable=False)
    by = Column(String(200), nullable=True)
    text = Column(Text, nullable=False)

    picking_list = relationship("PickingList", back_populates="history")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=_uuid)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=True)
    uploaded_by = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=_now)
