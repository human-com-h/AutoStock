# AGENTS.md — AutoStock 项目开发规范

本文件供 Codex 及协作者在本仓库中工作时遵循。业务背景与架构决策见 `docs/系统设计.md`，本文件只写"写代码时必须遵守的规则"，不重复设计说明书的完整内容，条目后括号标注对应章节，改代码前有疑问回那一节确认。

## 项目一句话说明

汽车零部件进销存管理系统：PC 端（FastAPI + Vue3/Element Plus，本地优先，SQLite）是数据中枢（Hub），手机端（Vue3/Vant + PWA + Dexie）是可完全离线的客户端，通过局域网 HTTPS 定期同步业务流水。

## 技术栈速查

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy / Pydantic / uvicorn / cryptography |
| PC 前端 | Vue3 + TypeScript + Element Plus + Pinia + ECharts |
| 手机前端 | Vue3 + TypeScript + Vant + Pinia + Dexie（IndexedDB）+ Workbox PWA |
| 数据库 | SQLite（WAL 模式），迁移用 Alembic |
| 共享代码 | `packages/shared`（TS 类型 + 业务规则纯函数 + 两端共用测试用例） |
| 打包 | PyInstaller（后端单 exe，内嵌 uvicorn 与两个前端静态资源） |

## 不可违反的核心约定

这些规则来自设计说明书的既定决策，写代码时不要"顺手优化"掉：

1. **主键**：所有业务表用 26 位 ULID 字符串，两端本地生成，禁止自增整数主键。（D1，§4.1）
2. **金额**：一律用 `INTEGER` 存"分"，禁止 REAL/FLOAT。仅前端展示时除以 100。（D6，§4.1）
3. **`stock_ledger` 是库存的唯一真相来源，append-only**：只能 INSERT，禁止 UPDATE/DELETE；写错了写一条反向流水冲正。`stock_snapshot` 是派生表，任何时候都能从流水重算，不能反过来当真相用。（§4.4）
4. **零件不可硬删除**：已产生流水的零件只能停用（`is_active=0`），未产生流水的才可软删除（`is_deleted=1`）。实现"删除零件"前必须先查有无关联流水。（D3）
5. **同步幂等与合并规则固定**：流水类写入按 `(source_type, source_id)` 或主键去重（`INSERT OR IGNORE` 语义），重复推送不能重复记账；主数据走行级 LWW（`updated_at` 大者胜，相等 PC 胜），被覆盖的旧值必须写入 `sync_conflict`，不能静默丢弃。（§7.3）
6. **公共字段不可缺省**：`id/created_at/updated_at/rev/version/device_id/is_deleted` 每张业务表都要有，`sync_status` 仅手机端表需要。新建表先对照 §4.1 检查。
7. **单据修改边界**：当日且未同步的单据可直接删除并回滚流水；其余一律走红冲（生成方向相反的新单据），不允许直接改历史单据内容。（§5.4）
8. **鉴权是必须项**：任何新增接口默认要求登录会话或 `device_token` 校验，不要因为"局域网环境"或"内部调试"跳过鉴权。（§8.1）
9. **手机端页面只读 IndexedDB**：新增手机端页面时数据来源必须是 Dexie 本地表，网络请求只负责把远端数据写入 IndexedDB，不允许接口响应直接拿去渲染。这是离线能力不出现"仅离线时才复现"的 bug 的关键约定。（§14.4）
10. **业务写入必须在单个数据库事务内完成**（生成单号、写主表、写明细、写流水、更新快照、`change_seq` 自增），保证断电或强杀不留下半条单据。（§12）
11. **不做扫码功能**（D8 已明确移除），零件检索只走编号/OE号/名称/拼音首字母。

## 代码组织

详见 `docs/项目目录结构.md`。核心原则：

- 后端按 `routers → services → sync/models/db` 分层：路由层不写业务逻辑，业务逻辑不直接拼 SQL（统一走 SQLAlchemy ORM）。
- 库存扣减、单据行校验等"两端都要算一遍"的逻辑写成纯函数放进 `packages/shared`：后端 Python 与手机端 TS 各自实现，但共用同一份规则说明与测试用例（相同输入必须得到相同输出），禁止两端逻辑分叉。（§3.3）
- PC 前端不做本地缓存/本地库，业务数据每次从接口取，Pinia 只放登录态、设置、字典缓存。（§9.2）

## 测试要求

- 新增/修改库存相关逻辑（入库、出库、退货、盘点、成本计算）必须补单元测试，覆盖移动加权成本多次波动后的精度场景。
- 数据一致性对账脚本（`stock_snapshot.quantity` 与 `stock_ledger` 求和逐件比对）是回归测试的红线，任何改动都不能让它变红。（§13）
- 涉及同步协议的改动，对照 §13 的用例表补测试（幂等重推、双端同改冲突、删除对修改、离线批量同步、断网重试）。
- 涉及证书/HTTPS/Service Worker 的改动，参照 §13 的离线能力真机用例做人工验证清单，不要只看单测通过就算完成。

## Git 提交约定

- 提交信息用中文动宾短语概括改动，例如"新增采购单红冲接口""修复移动加权成本精度问题"。
- 涉及第 0 节架构决策变更的提交，在提交信息中注明对应设计文档章节号。
- 不提交：`certs/`、`*.db`、`backups/`、`node_modules/`、`__pycache__/`、`.venv/`、构建产物目录。

## 禁止事项

- 不引入需要公网/云服务的依赖（本地优先、不买云服务器是明确前提）。
- 不用浮点类型存金额。
- 不对 `stock_ledger` 做 UPDATE/DELETE。
- 不跳过接口鉴权，哪怕是"内部调试用"的接口。
- 不做扫码相关功能。
- 不在没有明确指示时改动第 0 节已确认的架构决策；如确有必要变更，先和用户确认并同步更新设计文档，不要只改代码不改文档。

## 常用命令

脚手架尚未搭建，以下为规划命令，落地时在此处补全实际脚本路径：

- 后端启动：`cd backend && uvicorn app.main:app --reload`
- PC 前端：`cd web-pc && pnpm dev`
- 手机前端：`cd web-mobile && pnpm dev`
- 一致性对账：`cd backend && python -m scripts.reconcile`
- 打包 exe：`python scripts/build_exe.py`

## 参考文档

- 系统设计说明书：`docs/系统设计.md`
- 项目目录结构：`docs/项目目录结构.md`
- 推荐 MCP：`docs/推荐MCP列表.md`
- 推荐 Skill：`docs/推荐Skill列表.md`
- 开发任务拆分：`docs/开发任务拆分.md`
