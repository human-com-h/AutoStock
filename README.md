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

PC 开发地址为 `http://127.0.0.1:5173`。阶段二开始后，完整后端通过本地
HTTPS 启动：

```powershell
cd backend
.\.venv\Scripts\python.exe run_web.py
```

主服务监听 `https://0.0.0.0:8756`，`http://0.0.0.0:8757/ca.crt`
仅用于 Android 下载本地 CA；8757 的其它路径会跳转到 HTTPS。手机端开发地址为
`http://127.0.0.1:5174/m/`，接口由 Vite 代理到本机 HTTPS 后端。

## Web 生产构建

```powershell
.\backend\.venv\Scripts\Activate.ps1
python scripts\build_web.py
cd backend
python -m alembic upgrade head
python run_web.py
```

构建后 FastAPI 会托管 PC 页面 `/` 和手机页面 `/m`。数据库默认存放在
`%APPDATA%\AutoStock\autostock.db`；可通过 `AUTOSTOCK_DATA_DIR` 指定其他数据目录。

## Windows 单文件打包

```powershell
.\backend\.venv\Scripts\python.exe scripts\package_windows.py
```

产物为 `release/AutoStock.exe`。首次启动会自动执行数据库迁移、生成本地 CA 和
服务器证书，然后同时启动 8756 HTTPS 主服务与 8757 CA 下载/跳转服务。HTTPS
服务就绪后会自动打开默认浏览器；若程序已经运行，再次点击 EXE 只会打开现有
管理页面，不会重复启动服务。

## 验证

```powershell
cd backend
python -m pytest -q
cd ..
pnpm.cmd run build:pc
pnpm.cmd run build:mobile
python scripts\reconcile.py
```
