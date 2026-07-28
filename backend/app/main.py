from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.errors import register_exception_handlers
from app.routers import (
    auth,
    backups,
    brands,
    categories,
    customers,
    excel,
    health,
    orders,
    parts,
    reports,
    settings,
    stock,
    stock_takes,
    suppliers,
)

app = FastAPI(title="AutoStock", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(suppliers.router)
app.include_router(customers.router)
app.include_router(parts.router)
app.include_router(stock.router)
app.include_router(orders.router)
app.include_router(stock_takes.router)
app.include_router(settings.router)
app.include_router(reports.router)
app.include_router(excel.router)
app.include_router(backups.router)

_static_root = Path(__file__).resolve().parent / "static"
if (_static_root / "mobile").is_dir():
    app.mount("/m", StaticFiles(directory=_static_root / "mobile", html=True), name="mobile")
if (_static_root / "pc").is_dir():
    app.mount("/", StaticFiles(directory=_static_root / "pc", html=True), name="pc")
