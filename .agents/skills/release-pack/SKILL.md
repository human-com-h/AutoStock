---
name: release-pack
description: 构建前端、PyInstaller 打包后端为单文件 exe、校验可正常启动，生成可分发的安装包。三个阶段末尾交付物都要用到。
---

# 打包发布

## 现状

依赖任务 **0.2/0.3**（后端与前端工程骨架）与任务 **1.5.5**（打包脚本）尚未实现前，本 Skill 只做检查与引导。

## 执行步骤

1. 检查以下产物是否具备打包条件：
   - `web-pc/`、`web-mobile/` 能否 `pnpm build` 成功，产物是否落在 `backend/app/static` 对应目录（供 FastAPI StaticFiles 挂载）
   - `backend/` 是否有 PyInstaller 打包配置（`.spec` 文件或等价脚本）
   - 若均不存在，说明相应任务未完成，询问是否现在按《系统设计说明书》§2.3、§15 实现打包脚本
2. 若已具备，执行顺序：
   1. `pnpm -C web-pc build`、`pnpm -C web-mobile build`
   2. 确认静态产物已复制/挂载到后端可识别的路径
   3. `pyinstaller` 打包为单文件 `AutoStock.exe`（携带 `cryptography` 等依赖，注意 hidden-imports，尤其是 uvicorn 的异步驱动与 SQLAlchemy 方言）
   4. 打包产物落地后，**在一个干净的临时目录**（不是开发目录）里运行该 exe，避免误用开发环境残留的 `%APPDATA%/AutoStock` 数据
3. 冒烟测试（自动化部分）：
   - 进程能启动，且在数秒内 `GET https://127.0.0.1:8756/api/health` 返回 200
   - `GET https://127.0.0.1:8756/` 能拿到 PC 前端首页 HTML
   - `GET https://127.0.0.1:8756/m` 能拿到手机前端首页 HTML
   - 首次启动应在 `%APPDATA%/AutoStock/` 下生成 `autostock.db` 与 `certs/`
4. 以下几项需要人工/真机验证，Skill 只需在报告中提醒，不要假装已验证：
   - 开机自启注册是否生效 [手动]
   - 目标电脑（非开发机）上首次运行是否顺利 [手动]
5. 输出一份简短的打包报告：版本号、产物路径、冒烟测试结果、还需要人工验证的清单。
