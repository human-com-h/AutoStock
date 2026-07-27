# AutoStock 推荐 MCP 列表

给 Claude Code 在本项目开发过程中配置的 MCP Server 建议，按优先级排列。这些是辅助开发/调试的工具，产品运行时不依赖它们。

| 优先级 | MCP | 用途 | 使用场景 |
| --- | --- | --- | --- |
| P0 | sqlite | 直接连接 autostock.db 执行只读/受控查询 | 核对 stock_ledger 与 stock_snapshot 是否一致、排查同步冲突数据、验证迁移脚本效果，比每次写脚本更快 |
| P0 | playwright（或 puppeteer） | 浏览器自动化 | 验证 PC 端和手机端页面；重点验证 Service Worker 注册、PWA 安装、离线状态（断网后仍能打开页面）等第 14 章的关键行为，普通接口测试测不出这些 |
| P1 | context7 | 拉取库的最新文档/API | FastAPI、SQLAlchemy 2.x、Vue3、Vant、Element Plus、Dexie.js、Workbox 用法迭代较快，写代码前查一下避免用过时 API |
| P1 | fetch | 发起 HTTP 请求并解析响应 | 手工调试 /api/sync/push、/api/sync/pull 等接口的 JSON 结构是否符合设计文档 §8.2/§7.2 的约定 |
| P2 | git（若非内置能力） | 仓库历史查询、diff、blame | 排查某段同步逻辑的历史改动原因 |
| P2 | filesystem | 跨目录批量读写 | monorepo 有后端/两个前端/共享包四块，一般内置 Read/Write/Glob 已够用，仅当需要跨进程共享文件访问时才单独配置 |
| 可选 | sequential-thinking | 结构化推理 | 设计同步冲突合并算法、编号撞车处理这类分支较多的逻辑时，先把步骤显式列出来再动手写 |
| 暂不需要 | postgres / mysql 类 MCP | 云端数据库 | 项目明确本地优先、用 SQLite，等真正要迁移云端数据库时再引入 |

配置方式：在项目根目录的 .mcp.json 中声明，不要写入全局配置，保证团队其他协作者或 CI 环境不会因为缺少这些 MCP 而失败——它们都是开发期辅助工具，产品代码不依赖它们。

## 安装状态（2026-07-27）

已写入项目根目录 `.mcp.json`：

| MCP | 包 | 运行方式 | 备注 |
| --- | --- | --- | --- |
| playwright | `@playwright/mcp@latest` | `npx` | Chromium 浏览器二进制已通过 `npx playwright install chromium` 安装 |
| context7 | `@upstash/context7-mcp@latest` | `npx` | 走本机 Clash Verge 代理（`127.0.0.1:7897`），因 context7.com 在国内网络下不稳定 |
| fetch | `mcp-server-fetch` | `uvx` | 用官方 `--proxy-url` 参数走代理，而非环境变量，更可靠 |
| sequential-thinking | `@modelcontextprotocol/server-sequential-thinking@latest` | `npx` | 纯本地推理，不需要联网 |

用到的前置依赖：`uv`（已通过 `pip install uv` 安装，供 `uvx` 运行 Python 类 MCP Server）。

**sqlite 暂未加入 .mcp.json**：项目还没有 `autostock.db`（等任务 0.4 建库）。等数据库文件存在后，按下面配置追加到 `.mcp.json` 的 `mcpServers` 里即可：

```json
"sqlite": {
  "command": "uvx",
  "args": ["mcp-server-sqlite", "--db-path", "<autostock.db 的绝对路径>"]
}
```

开发环境通常指向 `%APPDATA%/AutoStock/autostock.db`；也可以额外配一份指向测试库（如 `backend/tests/fixtures/*.db`），方便对账类调试。

git / filesystem 两项维持"暂不单独配置"的结论：Claude Code 内置的 Bash/Read/Write/Glob/Grep 已覆盖日常需求。
