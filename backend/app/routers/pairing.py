from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth, require_device_auth
from app.db.session import get_db
from app.schemas.pairing import PairingExchange
from app.services import bootstrap_service, pairing_service

router = APIRouter(tags=["pairing"])


@router.post("/api/pairing/code", dependencies=[Depends(require_auth)])
def create_pairing_code(db: Session = Depends(get_db)):
    return success_body(data=pairing_service.create_pairing_code(db))


@router.get("/api/pairing/qr", dependencies=[Depends(require_auth)])
def pairing_qr(content: str = Query(min_length=1, max_length=500)):
    image = qrcode.make(content)
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/api/pairing/exchange")
def exchange_pairing_code(payload: PairingExchange, db: Session = Depends(get_db)):
    return success_body(
        data=pairing_service.exchange_pairing_code(
            db,
            payload.code,
            payload.device_name,
            payload.client_time,
        )
    )


@router.post("/api/auth/pair")
def exchange_pairing_code_alias(
    payload: PairingExchange,
    db: Session = Depends(get_db),
):
    """设计文档中的稳定路径；保留 /api/pairing/exchange 兼容已生成的二维码。"""
    return exchange_pairing_code(payload, db)


@router.get(
    "/api/mobile/bootstrap/parts",
    dependencies=[Depends(require_device_auth)],
)
def bootstrap_parts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return success_body(data=bootstrap_service.parts_page(db, offset, limit))


@router.get(
    "/api/mobile/bootstrap/master-data",
    dependencies=[Depends(require_device_auth)],
)
def bootstrap_master_data(db: Session = Depends(get_db)):
    return success_body(data=bootstrap_service.master_data(db))


@router.get(
    "/api/mobile/bootstrap/orders",
    dependencies=[Depends(require_device_auth)],
)
def bootstrap_orders(db: Session = Depends(get_db)):
    return success_body(data=bootstrap_service.recent_orders(db))
