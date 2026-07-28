# AutoStock

汽车零部件进销存 Web 系统。PC 管理端使用 Vue 3 + Element Plus，后端使用
FastAPI + SQLAlchemy + SQLite。

## 开发启动

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8756
```

另开终端启动 PC 前端：

```powershell
pnpm.cmd run dev:pc
```

PC 开发地址为 `http://127.0.0.1:5173`，接口由 Vite 代理到
`http://127.0.0.1:8756`。

## Web 生产构建

```powershell
.\backend\.venv\Scripts\Activate.ps1
python scripts\build_web.py
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8756
```

构建后 FastAPI 会托管 PC 页面 `/` 和手机页面 `/m`。数据库默认存放在
`%APPDATA%\AutoStock\autostock.db`；可通过 `AUTOSTOCK_DATA_DIR` 指定其他数据目录。

## 验证

```powershell
cd backend
python -m pytest -q
cd ..
pnpm.cmd run build:pc
pnpm.cmd run build:mobile
python scripts\reconcile.py
```
