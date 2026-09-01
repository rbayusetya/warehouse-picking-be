from __future__ import annotations
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import init_db, async_session_factory
from app.routers import auth, picking, debts, dealer, settlement_handover
from app.services.auth_service import hash_password
from app.models import User


async def _seed_users():
    async with async_session_factory() as db:
        stmt = select(User).limit(1)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return

        users = [
            User(username="admin", password_hash=hash_password("admin123"),
                 name="Admin Gudang", role="admin", role_label="Admin Gudang"),
            User(username="kepala", password_hash=hash_password("kepala123"),
                 name="Kepala Gudang", role="kepala", role_label="Kepala Gudang"),
            User(username="tunas", password_hash=hash_password("tunas123"),
                 name="Pengurus Tunas Muda", role="ekspedisi", role_label="Pengurus Ekspedisi",
                 expedition="TUNAS MUDA"),
            User(username="jagat", password_hash=hash_password("jagat123"),
                 name="Pengurus Jagat", role="ekspedisi", role_label="Pengurus Ekspedisi",
                 expedition="JAGAT"),
            User(username="dealer-lecf", password_hash=hash_password("lecf123"),
                 name="Dealer TRIDJAYA", role="dealer", role_label="Dealer",
                 dealer_code="LECF"),
            User(username="dealer-lech", password_hash=hash_password("lech123"),
                 name="Dealer DEASSY", role="dealer", role_label="Dealer",
                 dealer_code="LECH"),
            User(username="dealer-kcey", password_hash=hash_password("kcey123"),
                 name="Dealer PT MITRA UTAMA", role="dealer", role_label="Dealer",
                 dealer_code="KCEY"),
        ]
        for u in users:
            db.add(u)
        await db.commit()
        print("  ✓ Seed users created")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing database...")
    await init_db()
    await _seed_users()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(picking.router)
app.include_router(debts.router)
app.include_router(dealer.router)
app.include_router(settlement_handover.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
