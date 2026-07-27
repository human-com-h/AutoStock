from fastapi import APIRouter

from app.core.errors import success_body
from app.core.version import APP_VERSION
from app.sync.change_seq import get_current_rev

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    return success_body(data={"version": APP_VERSION, "status": "ok"}, server_rev=get_current_rev())
