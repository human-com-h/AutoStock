---
name: reconcile
description: 一键跑库存一致性对账（stock_snapshot 与 stock_ledger 求和逐件比对），汇总并展示差异。库存相关代码改动后、每个任务提交前、阶段验收前都应跑一次。
---

# 库存一致性对账

## 现状

依赖任务 **1.2.5**（`scripts/reconcile.py`）尚未实现前，本 Skill 只做检查与引导，不假装能跑出结果。

## 执行步骤

1. 检查 `scripts/reconcile.py` 是否存在。
   - **不存在**：说明任务 1.2.5 还没做。告知用户依赖任务未完成，并询问是否现在按《系统设计说明书》§4.4、§13 的对账口径实现它：
     - 对每个 `part_id`，`SUM(stock_ledger.quantity) == stock_snapshot.quantity`（含 `is_deleted` 处理与并发写入下的一致性读取）。
     - 输出不一致的 `part_id`、账面快照值、流水求和值、差值，按差值绝对值降序排列。
     - 退出码：全部一致为 0，存在不一致为非 0（供 CI 使用）。
   - **存在**：继续下一步。
2. 定位数据库文件（默认 `%APPDATA%/AutoStock/autostock.db`，测试环境可能是项目内的 `backend/tests/*.db`），确认可读。
3. 运行脚本（例如 `python scripts/reconcile.py --db <path>`），捕获输出。
4. 汇总展示：
   - 总零件数、不一致件数、不一致占比。
   - 差异最大的前 10 条，附 `part_id`、零件名称（如可关联查到）、快照值、流水求和值、差值。
   - 若全部一致，明确告知"对账通过，0 处差异"。
5. 若发现不一致，不要自作主张修复数据；报告给用户，并提示可能原因（如某条流水写入后快照未同步更新、并发写入竞态、重算未触发等），交由用户决定是否执行 `POST /api/stock/recalculate`（任务 1.2.4）重建快照。
