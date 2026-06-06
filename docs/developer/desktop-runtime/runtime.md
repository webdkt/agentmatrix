# Runtime — Desktop 运行时总控

Runtime（`AgentMatrix` 类）是 Desktop 场景的总控模块。它负责初始化整个系统、加载 Agent、管理生命周期、收集状态，并向前端推送事件。

---

## 初始化流程

Runtime 启动时按以下顺序初始化：

1. **路径初始化**：根据 `--matrix-world` 参数确定工作空间根目录，创建必要的子目录（配置、日志、数据库、文件工作区等）
2. **清理孤儿进程**：检查并终止上次异常退出遗留的 Chrome 进程（浏览器自动化相关）
3. **数据库连接**：初始化 SQLite 数据库连接（邮件存储、定时任务）
4. **PostOffice 创建**：初始化邮件总线，准备接收和分发邮件
5. **系统状态收集器**：启动后台任务，定期收集系统运行状态
6. **Agent 加载**：遍历 Agent 配置目录，加载所有 Agent
7. **事件循环启动**：启动异步事件循环，Agent 开始监听邮件

---

## Agent 加载

Runtime 从 MatrixWorld 的 `agents/` 目录加载 Agent 配置。每个 Agent 对应一个 YAML 配置文件，包含名称、描述、人设、技能列表和模型配置。

加载过程：

1. 读取配置文件并验证格式
2. 创建 BaseAgent 实例
3. 为 BaseAgent 注入 Brain 和 Cerebellum（根据配置的模型）
4. 将 BaseAgent 注册到 PostOffice
5. 启动 BaseAgent 的主循环（开始监听邮件）

如果某个 Agent 的配置有问题（如引用了不存在的技能），Runtime 会记录错误并跳过该 Agent，不影响其他 Agent 的加载。

---

## 生命周期管理

Runtime 管理整个系统的生命周期：

### 启动

- 解析命令行参数
- 按初始化流程逐步启动
- 向 Tauri 前端写入后端服务端口号（用于端口发现）

### 运行

- 所有 Agent 处于监听状态
- PostOffice 接收和分发邮件
- 系统状态收集器定期更新
- 前端通过 HTTP/WebSocket 与后端交互

### 优雅关闭

- 接收 SIGTERM 或 SIGINT 信号
- 通知所有 Agent 停止接收新邮件
- 等待正在执行的任务完成当前动作
- 保存所有会话状态到 SessionStore
- 关闭数据库连接
- 关闭 PostOffice
- 释放所有资源

---

## 系统状态收集

Runtime 维护一个系统状态收集器，定期收集以下信息：

- 各 Agent 的当前状态（空闲、思考中、工作中等）
- 系统资源使用情况（CPU、内存）
- 邮件队列长度
- 容器运行状态

这些状态通过事件总线推送到前端，用于实时显示 Agent 状态和系统健康度。

---

## 事件总线

Runtime 维护一个事件总线，连接各个子系统：

- **Agent 事件**：状态变化、任务完成、错误等
- **PostOffice 事件**：邮件收发、队列状态
- **系统事件**：资源使用、配置变更

前端通过 WebSocket 订阅这些事件，实现实时状态更新。事件总线也支持注册自定义回调，方便扩展。

---

## 与 Core 层的关系

Runtime 建立在 Core 层之上，但增加了 Desktop 场景特有的功能：

| | Core 层 | Desktop Runtime |
|--|---------|-----------------|
| Agent 实现 | BasicAgent | BaseAgent |
| 通信 | 抽象的 Signal | 具体的 Email + PostOffice |
| 持久化 | SessionStore 接口 | SQLite + 文件系统 |
| 隔离 | 无 | Docker/Podman 容器 |
| 用户交互 | Shell 协议 | Desktop App / 邮件代理 |
| 生命周期 | 单任务 | 长期运行 + 优雅关闭 |

Runtime 是 Core 层的一个具体应用场景。如果你不需要 Desktop 的功能（如邮件系统、容器隔离、前端界面），可以直接使用 Core 层构建更轻量的应用。
