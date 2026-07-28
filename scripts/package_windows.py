"""构建 Web 静态资源并打包 Windows 单文件 AutoStock.exe。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from build_web import build_web

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RELEASE_DIR = ROOT / "release"
WORK_DIR = ROOT / "build" / "pyinstaller"


def package() -> Path:
    build_web()
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(RELEASE_DIR),
            "--workpath",
            str(WORK_DIR),
            str(BACKEND / "autostock.spec"),
        ],
        cwd=BACKEND,
        check=True,
    )
    artifact = RELEASE_DIR / "AutoStock.exe"
    if not artifact.is_file():
        raise FileNotFoundError(f"打包未生成预期产物：{artifact}")
    return artifact


if __name__ == "__main__":
    print(f"Windows 单文件打包完成：{package()}")
