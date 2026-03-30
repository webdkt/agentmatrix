# 故障排除

常见问题及其解决方案。

## 应用无法启动

**症状**：应用窗口不出现，或立即崩溃。

**解决方案**：

- 验证所有前置条件已安装：Node.js 18+、Python 3.10+、Rust 工具链
- 检查 5173 端口是否未被其他应用占用
- 尝试删除 `node_modules` 并重新运行 `npm install`
- 检查终端输出中的具体错误消息

## 后端未启动

**症状**：应用启动但智能体无响应，或显示"后端已断开"状态。

**解决方案**：

- 验证 Python 3.10+ 已安装并在 PATH 中：`python3 --version`
- 检查 `~/.agentmatrix/settings.json` 中 `auto_start_backend` 是否为 `true`
- 尝试手动启动后端以查看错误输出
- 确保 Matrix World 目录存在且包含 `.matrix/configs/`
- 检查 configs 目录中是否存在 `llm_config.json`

## WebSocket 断开连接

**症状**："已断开"状态指示器，无实时更新，新邮件不出现。

**解决方案**：

- 确认后端正在 8000 端口运行
- 检查防火墙或安全软件 —— 可能阻止 WebSocket 连接
- 重启应用以强制重新连接
- 应用会自动重试连接，最多 5 次

## LLM 配置错误

**症状**：智能体响应出现错误，或向导在模型配置步骤失败。

**解决方案**：

- 验证您的 API 密钥正确且未过期
- 检查 API 基础 URL 是否与提供商文档一致
- 确保模型名称拼写正确（如 `gpt-4o`，而非 `GPT-4`）
- 使用直接 curl 请求测试 API 密钥
- 对于自定义端点，确保服务器正在运行且可访问

## Podman / Docker 未找到

**症状**：关于容器运行时不可用的警告。

**解决方案**：

- 在系统上安装 Podman（首选）或 Docker
- 在 macOS 上运行 `podman machine init && podman machine start`
- 验证安装：`podman --version` 或 `docker --version`
- 安装容器运行时后重启 AgentMatrix

## 邮件代理连接失败

**症状**：邮件代理设置中的"测试连接"失败。

**解决方案**：

- 仔细检查 IMAP/SMTP 主机名和端口
- 对于 Gmail，使用应用专用密码而非普通密码
- 确保您的邮箱提供商允许 IMAP/SMTP 访问（某些提供商需要在设置中启用）
- 检查网络是否阻止了所需端口（IMAP 为 993，SMTP 为 587）
- 尝试用桌面邮件客户端（如 Thunderbird）连接以验证凭据

## 通知未出现

**症状**：新邮件到达时没有桌面通知。

**解决方案**：

- 检查 `~/.agentmatrix/settings.json` 中 `enable_notifications` 是否为 `true`
- 在操作系统设置中授予 AgentMatrix 通知权限
- macOS：系统偏好设置 > 通知 > AgentMatrix
- Windows：设置 > 系统 > 通知 > AgentMatrix

## 配置文件损坏

**症状**：手动编辑配置后应用无法启动或行为异常。

**解决方案**：

- 验证 YAML 文件的语法（正确的缩进，无制表符）
- 验证 JSON 文件（匹配的括号，正确的引号）
- 从备份恢复或删除文件以触发默认值
- 作为最后手段，删除 `~/.agentmatrix/settings.json` 以重新运行向导
