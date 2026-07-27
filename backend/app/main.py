from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.errors import register_exception_handlers
from app.routers import (
    auth,
    brands,
    categories,
    customers,
    health,
    orders,
    parts,
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
