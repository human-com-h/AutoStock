from __future__ import annotations

import json
import ssl
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import uvicorn
from alembic import command
from alembic.config import Config as AlembicConfig

from app.core.certs import ensure_certificates
from app.core.config import settings
from app.main import app as main_app
from app.redirect_app import app as redirect_app

LOCAL_URL = f"https://127.0.0.1:{settings.port_https}"
HEALTH_URL = f"{LOCAL_URL}/api/health"


def _run_redirect_server() -> None:
    uvicorn.run(
        redirect_app,
        host="0.0.0.0",
        port=settings.port_http,
        log_level="warning",
    )


def _resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    return Path(bundled_root) if bundled_root else Path(__file__).resolve().parent


def _run_migrations() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    root = _resource_root()
    config = AlembicConfig(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


def _health_ready(timeout_seconds: float = 0.8) -> bool:
    try:
        context = ssl._create_unverified_context()
        with urlopen(HEALTH_URL, timeout=timeout_seconds, context=context) as response:
            payload = json.load(response)
        return (
            response.status == 200
            and payload.get("data", {}).get("status") == "ok"
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _open_browser() -> None:
    try:
        webbrowser.open(LOCAL_URL, new=2)
    except webbrowser.Error as exc:
        print(f"无法自动打开浏览器，请手动访问 {LOCAL_URL}：{exc}", file=sys.stderr)


def _open_browser_when_ready(
    attempts: int = 40,
    interval_seconds: float = 0.25,
) -> None:
    for _ in range(attempts):
        if _health_ready():
            _open_browser()
            return
        time.sleep(interval_seconds)
    print(f"服务已经启动，请手动访问 {LOCAL_URL}", file=sys.stderr)


def main() -> None:
    if _health_ready():
        print("AutoStock 已在运行，正在打开管理页面。")
        if settings.open_browser_on_start:
            _open_browser()
        return

    _run_migrations()
    bundle = ensure_certificates()
    redirect_thread = threading.Thread(target=_run_redirect_server, daemon=True)
    redirect_thread.start()
    if settings.open_browser_on_start:
        browser_thread = threading.Thread(
            target=_open_browser_when_ready,
            daemon=True,
        )
        browser_thread.start()
    uvicorn.run(
        main_app,
        host="0.0.0.0",
        port=settings.port_https,
        ssl_keyfile=str(bundle.server_key),
        ssl_certfile=str(bundle.server_cert),
    )


if __name__ == "__main__":
    main()
