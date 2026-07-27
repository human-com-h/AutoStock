# AutoStock

汽车零部件进销存管理系统。设计文档见 `docs/系统设计.md`，开发规范见 `CLAUDE.md`。

## 启动

```bash
# 后端
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# PC 前端
cd web-pc
pnpm install
pnpm dev

# 手机前端
cd web-mobile
pnpm install
pnpm dev
```

## 一致性对账

```bash
cd backend
python -m scripts.reconcile
```
