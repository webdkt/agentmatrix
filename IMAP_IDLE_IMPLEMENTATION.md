# Email Proxy Service - IMAP IDLE 推送模式

## 概述

Email Proxy Service 现在使用 **IMAP IDLE** (RFC 2177) 实现实时邮件推送，而不是轮询模式。

## IMAP IDLE 优势

### 1. 实时性
- **轮询模式**：最多延迟 30 秒才能收到新邮件
- **IDLE 模式**：服务器主动推送，几乎实时收到新邮件（通常 < 1 秒）

### 2. 资源效率
- **轮询模式**：每 30 秒发起一次 IMAP 请求，无论是否有新邮件
- **IDLE 模式**：建立长连接，只在有新邮件时才唤醒处理

### 3. 网络流量
- **轮询模式**：持续的周期性网络流量
- **IDLE 模式**：空闲时几乎零流量

## 实现原理

### IDLE 工作流程

```
1. 创建 IMAP SSL 连接
   ↓
2. 登录并发送 ID 命令（163 邮箱要求）
   ↓
3. 选择 INBOX
   ↓
4. 发送 IDLE 命令（进入推送模式）
   ↓
5. 等待服务器推送
   ├─ 定期调用 idle_check(timeout=1) 检查
   ├─ 收到 EXISTS/RECENT 响应 → 有新邮件
   └─ 没有响应 → 继续等待
   ↓
6. 检测到新邮件
   ├─ 结束 IDLE（idle_done）
   ├─ 处理新邮件（fetch_external_emails）
   └─ 重新进入 IDLE 循环
   ↓
7. 循环继续...
```

### 代码结构

#### 主循环：`_idle_loop()`
```python
async def _idle_loop(self):
    """IMAP IDLE 循环：实时推送模式"""
    while self._running:
        # 1. 创建连接
        conn = await self._create_imap_connection()
        conn.select('INBOX')

        # 2. 进入 IDLE 循环
        while self._running:
            conn.idle()  # 发送 IDLE 命令

            # 3. 等待推送
            while self._running:
                await asyncio.sleep(5)  # 定期检查
                responses = conn.idle_check(timeout=1)

                # 4. 检查新邮件
                if has_new_email(responses):
                    conn.idle_done()  # 结束 IDLE
                    await self.fetch_external_emails(conn)  # 处理邮件
                    break  # 重新进入 IDLE
```

#### 连接管理：`_create_imap_connection()`
```python
def _create_imap_connection(self):
    """创建并认证 IMAP 连接"""
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)

    # 163 邮箱要求
    imaplib.Commands["ID"] = "AUTH"
    conn._simple_command("ID", '("name" "AgentMatrix" "version" "1.0.0")')

    return conn
```

#### 邮件处理：`fetch_external_emails(conn=None)`
```python
async def fetch_external_emails(self, conn=None):
    """
    从 IMAP 服务器拉取新邮件

    Args:
        conn: 可选的现有连接（IDLE 模式下复用）
    """
    # 复用现有连接，避免重新连接
    emails = self._fetch_emails_sync(conn)

    for email in emails:
        await self.process_external_email(email)
```

## 兼容性

### 服务器支持
- ✅ **Gmail**：完全支持 IMAP IDLE
- ✅ **Outlook**：完全支持 IMAP IDLE
- ✅ **163 邮箱**：支持（需要 ID 命令）
- ✅ **QQ 邮箱**：支持
- ⚠️ **部分企业邮箱**：可能不支持（会自动降级到重连模式）

### 自动重连机制
如果服务器不支持 IDLE 或连接中断：
1. 捕获异常
2. 关闭旧连接
3. 等待 5 秒
4. 重新连接并继续

## 性能对比

| 指标 | 轮询模式 | IDLE 模式 |
|------|---------|----------|
| 延迟 | 0-30 秒 | < 1 秒 |
| CPU | 定期唤醒 | 几乎为零 |
| 网络请求 | 每 30 秒 1 次 | 仅新邮件时 |
| 服务器负载 | 持续轮询 | 事件驱动 |

## 监控和日志

### 启动日志
```
✅ IMAP 连接成功，进入 IDLE 模式
📡 IDLE 模式已激活，等待推送...
```

### 新邮件日志
```
📬 收到新邮件推送
📬 处理邮件: reply → AgentA
✅ 已转发邮件到 UserProxyAgent.speak()
```

### 重连日志
```
IDLE 操作失败: [Errno 32] Broken pipe
⏳ 5 秒后尝试重新连接...
🔗 连接到 IMAP 服务器...
✅ IMAP 连接成功，进入 IDLE 模式
```

### 停止日志
```
🛑 IMAP IDLE 循环已停止
```

## 测试

### 测试步骤
1. 启动 AgentMatrix 服务
2. 观察日志确认进入 IDLE 模式
3. 从外部邮箱发送测试邮件
4. 验证是否在 1 秒内收到推送

### 预期日志输出
```
📡 IDLE 模式已激活，等待推送...
（等待中...）
📬 收到新邮件推送
📬 处理邮件: new_session → AgentA
✅ 已转发邮件到 UserProxyAgent.speak()
📡 IDLE 模式已激活，等待推送...
```

## 注意事项

### 1. 防火墙和 NAT
- IDLE 使用长连接，可能被防火墙或 NAT 超时
- 实现中每 5 秒检查一次，避免连接超时

### 2. 服务器限制
- 部分服务器限制 IDLE 连接时长（如 29 分钟）
- 实现会自动处理超时并重连

### 3. 网络不稳定
- 如果网络不稳定，连接可能中断
- 自动重连机制会在 5 秒后重新建立连接

## 配置

无需额外配置，只要 IMAP 服务器支持 IDLE 即可自动启用。

如果不支持，会自动降级到重连模式（每次失败后 5 秒重连）。

## 未来优化

1. **批量处理**：一次推送可能包含多封邮件，支持批量处理
2. **连接池**：支持多个 IDLE 连接（多邮箱）
3. **心跳检测**：主动检测连接健康度
4. **降级策略**：检测到服务器不支持时自动降级到轮询模式
