from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.errors import success_body
from app.core.security import require_auth
from app.db.session import get_db
from app.services import excel_service

router = APIRouter(
    prefix="/api/excel",
    tags=["excel"],
    dependencies=[Depends(require_auth)],
)


def _download(content: bytes, filename: str) -> StreamingResponse:
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/template/parts")
def download_part_template():
    return _download(excel_service.part_template(), "零件导入模板.xlsx")


@router.get("/export/parts")
def download_parts(db: Session = Depends(get_db)):
    return _download(excel_service.export_parts(db), "零件档案.xlsx")


@router.get("/export/inventory")
def download_inventory(db: Session = Depends(get_db)):
    return _download(excel_service.export_inventory(db), "库存查询.xlsx")


@router.get("/export/orders/purchases")
def download_purchase_orders(db: Session = Depends(get_db)):
    return _download(excel_service.export_orders(db, "purchase"), "采购明细.xlsx")


@router.get("/export/orders/sales")
def download_sales_orders(db: Session = Depends(get_db)):
    return _download(excel_service.export_orders(db, "sales"), "销售明细.xlsx")


@router.get("/export/ledger")
def download_stock_ledger(db: Session = Depends(get_db)):
    return _download(excel_service.export_stock_ledger(db), "库存台账.xlsx")


@router.get("/export/summary")
def download_stock_summary(db: Session = Depends(get_db)):
    return _download(excel_service.export_stock_summary(db), "进销存汇总.xlsx")


@router.post("/import/parts")
async def upload_parts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    result = excel_service.import_parts(db, await file.read())
    return success_body(data=result)
