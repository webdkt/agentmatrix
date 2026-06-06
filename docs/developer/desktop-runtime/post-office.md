# PostOffice — 邮件总线

PostOffice 是 Desktop 运行时的邮件路由中心。所有 Agent 之间的通信——无论是用户给 Agent 发任务，还是 Agent 之间协作——都必须经过 PostOffice。

---

## 定位

PostOffice 不是简单的消息队列。它是 AgentMatrix 中 Agent 发现、注册、通信和持久化的统一入口。

每个 Agent 在启动时向 PostOffice 注册，注销时从 PostOffice 移除。PostOffice 维护着一份当前系统中所有活跃 Agent 的目录。

---

## 核心功能

### Agent 注册与发现

Agent 启动时调用 `register()` 方法向 PostOffice 登记。登记信息包括 Agent 名称和描述。

PostOffice 维护的 Agent 目录被称为「黄页」(Yellow Page)。任何 Agent 都可以通过黄页查询系统中还有哪些 Agent、它们是做什么的。这使得 Agent 能够动态发现协作者，而不需要硬编码其他 Agent 的名称。

### 邮件接收

PostOffice 提供一个异步队列。所有要发送的邮件都被放入这个队列，PostOffice 按顺序处理。

### 邮件持久化

每封邮件在分发前都会被写入 SQLite 数据库。这保证了：

- 系统重启后邮件不会丢失
- 可以查询历史邮件
- 可以按会话或任务检索邮件

### 邮件分发

PostOffice 根据邮件的收件人字段，将邮件投递到对应 Agent 的 inbox（输入队列）。如果收件人 Agent 不存在，邮件会被标记为失败并记录日志。

### 暂停与恢复

PostOffice 可以被整体暂停。暂停期间，邮件仍然会被接收和持久化，但不会分发给 Agent。这在系统维护或批量配置更新时很有用。恢复后，积压的邮件会按顺序分发。

---

## 黄页机制

黄页是 PostOffice 提供的 Agent 发现服务。Agent 可以通过以下方式查询：

- **完整黄页**：列出所有注册的 Agent 及其描述
- **排除自己**：列出除自己之外的所有 Agent
- **联系人列表**：只返回名称列表

Agent 在需要与其他 Agent 协作时，先查询黄页了解有哪些可用的协作者，然后选择合适的 Agent 发送邮件。

黄页信息是动态的：Agent 启动时自动加入，停止时自动移除。

---

## 邮件生命周期

一封邮件在系统中的完整生命周期：

1. **生成**：发件 Agent 创建邮件对象，填充发件人、收件人、主题、正文、任务 ID、会话 ID 等字段
2. **投递**：发件 Agent 将邮件交给 PostOffice
3. **持久化**：PostOffice 将邮件写入数据库
4. **分发**：PostOffice 根据收件人查找目标 Agent，将邮件放入其 inbox
5. **处理**：收件 Agent 从 inbox 取出邮件，创建/复用 MicroAgent 处理
6. **回复**：收件 Agent 生成回复邮件，再次交给 PostOffice
7. **接收**：发件 Agent（或用户）收到回复

---

## 与用户代理的集成

UserProxy 是一个特殊的 Agent，代表人类用户。当用户通过 Desktop App 发送邮件时，实际上是通过 UserProxy 发送的。PostOffice 对 UserProxy 和其他 Agent 一视同仁——UserProxy 也在黄页中注册，也接收和发送邮件。

当配置了邮件代理时，邮件代理从真实邮箱读取邮件后，也是通过 PostOffice 分发给目标 Agent。Agent 的回复同样经过 PostOffice，由邮件代理转发回用户的真实邮箱。

---

## 扩展性

PostOffice 的设计允许以下扩展：

- **多实例**：在分布式部署中，可以多个 PostOffice 实例共享同一个数据库后端
- **优先级队列**：可以为不同类型的邮件设置优先级（如系统邮件优先于用户邮件）
- **邮件过滤**：可以在分发前添加过滤器，拦截或修改特定邮件
- **统计与监控**：可以扩展邮件流量统计、延迟监控等功能
