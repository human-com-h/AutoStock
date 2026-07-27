---
name: cert-check
description: 检查 AutoStock 本地 CA、服务器证书 SAN 与过期时间、8756/8757 端口连通性。第 14 章证书链路相关改动后、手机连不上时使用。
---

# 证书与端口自检

## 现状

依赖任务 **2.1**（后端自动生成本地 CA 与服务器证书）尚未实现前，本 Skill 只做检查与引导。

## 执行步骤

1. 确认证书文件是否存在：
   - CA 私钥：`%APPDATA%/AutoStock/certs/ca.key`
   - CA 证书、服务器证书（具体文件名以任务 2.1 实现为准）
   - 若目录或文件不存在，告知用户任务 2.1 未完成或后端从未启动过，询问是否现在按《系统设计说明书》§14.2 实现证书自动生成逻辑。
2. 若证书存在，用 Python `cryptography` 库（不依赖 openssl 命令行，与后端保持一致）读取服务器证书，输出：
   - Subject / Issuer
   - SAN 列表（应包含本机所有内网 IP、127.0.0.1、localhost、autostock.local）
   - 有效期起止，若剩余不足 30 天要高亮提醒
   - 签发者是否为本机的 AutoStock Local CA
3. 检查本机实际网卡 IP，对比是否都已在 SAN 内；若发现新 IP 不在 SAN 内，说明重签逻辑（§14.2 第②⑤条）未触发或有 bug。
4. 端口连通性：
   - `curl -sk https://127.0.0.1:8756/api/health`，确认 HTTPS 正常且返回 `server_rev`
   - `curl -s http://127.0.0.1:8757/ca.crt -o /dev/null -w '%{http_code}'`，确认证书下载端口可用
   - 若均失败，检查 Windows 防火墙 8756/8757 入站规则是否放行（§14.7）
5. 汇总一份简短报告：CA 状态、服务器证书状态、SAN 覆盖情况、两个端口的连通性，任何一项异常都要明确指出具体原因而不是笼统说"有问题"。
