"""构建 PC/手机 Web 前端，并复制到 FastAPI 的静态资源目录。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "backend" / "app" / "static"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def build_web() -> Path:
    package_manager = "pnpm.cmd" if sys.platform == "win32" else "pnpm"
    run(package_manager, "run", "build:pc")
    run(package_manager, "run", "build:mobile")

    for name, source in (
        ("pc", ROOT / "web-pc" / "dist"),
        ("mobile", ROOT / "web-mobile" / "dist"),
    ):
        destination = STATIC_ROOT / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
    return STATIC_ROOT


if __name__ == "__main__":
    print(f"Web 构建完成：{build_web()}")
