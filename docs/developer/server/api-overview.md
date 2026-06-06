# FastAPI Server 概览

AgentMatrix 的后端服务基于 FastAPI 构建，提供 REST API 和 WebSocket 实时通信。Desktop App 的前端通过 HTTP 请求和 WebSocket 连接与后端交互。

---

## 职责

FastAPI Server 的职责是：

- 接收前端的 HTTP 请求（发送邮件、查询会话、管理配置等）
- 通过 WebSocket 向前端推送实时事件（Agent 状态变化、执行进度等）
- 管理应用生命周期（启动时初始化 Runtime，关闭时清理资源）
- 提供 CORS 支持，允许 Tauri 前端跨域访问

Server 本身不包含业务逻辑，业务逻辑全部委托给 AgentMatrix Runtime 和各个服务模块。

---

## 路由模块

API 按功能划分为多个路由模块：

| 路由 | 职责 |
|------|------|
| agents | Agent 的 CRUD、状态查询、启停控制 |
| sessions | 会话列表、邮件历史、分页查询 |
| skills | 技能列表、技能详情 |
| config | 系统配置读写、LLM 配置管理 |
| llm_configs | LLM 模型的增删改查 |
| proxy | HTTP 代理配置 |
| email_proxy | 邮件代理配置和状态 |
| system | 系统状态、健康检查 |
| websocket | WebSocket 连接管理、事件推送 |

每个路由模块只处理请求参数的解析和响应的序列化，具体的业务逻辑调用对应的服务层方法。

---

## 生命周期

Server 的生命周期由 FastAPI 的 Lifespan 机制管理：

### 启动阶段

1. 解析命令行参数（矩阵世界路径、主机、端口等）
2. 初始化共享路径状态
3. 创建 FastAPI 应用实例
4. 注册路由和中间件
5. 启动 Uvicorn 服务器
6. 将实际监听的端口号写入文件（供 Tauri 发现）

### 关闭阶段

1. 接收 SIGTERM 或 SIGINT 信号
2. 触发 Lifespan 的关闭回调
3. 通知 Runtime 优雅关闭
4. 等待所有 Agent 完成当前动作
5. 保存会话状态
6. 关闭数据库连接
7. 释放资源

---

## 与 Tauri 前端的端口发现

Desktop App 的 Tauri 前端需要知道后端服务运行在哪个端口。由于端口可能是动态分配的（使用端口 0 让操作系统分配），后端在启动后会：

1. 获取实际监听的端口号
2. 将端口号写入 MatrixWorld 的 `.matrix/backend_port` 文件
3. 前端启动时读取这个文件，知道后端的实际地址

这种机制避免了硬编码端口，允许同时运行多个实例。

---

## 中间件

Server 配置了以下中间件：

### CORS

允许 Tauri 前端跨域访问。由于 Tauri 应用加载的是本地文件，请求来源是 `tauri://localhost` 或类似地址，需要显式允许。

### 请求计时

记录每个请求的处理时间。如果请求超过 100ms，会在日志中标记为慢请求，帮助识别性能瓶颈。

---

## 部署方式

FastAPI Server 可以通过以下方式运行：

### 开发模式

```bash
python server.py --matrix-world ./MatrixWorld --reload
```

开发模式启用自动重载，代码修改后服务会自动重启。适合开发和调试。

### 生产模式

```bash
python server.py --matrix-world ./MatrixWorld --host 0.0.0.0
```

生产模式下不使用重载，建议配合进程管理器（如 systemd、supervisor）运行。

### 作为模块导入

Server 应用可以作为模块导入：

```python
from server import app
# app 是配置好的 FastAPI 实例
```

这允许在其他 ASGI 服务器（如 Gunicorn + Uvicorn）中运行，或嵌入到更大的应用中。

---

## 扩展 API

如果你需要为前端或其他客户端提供新的 API：

1. 在 `server_handlers/routes/` 下创建新的路由模块
2. 在模块中定义路由处理函数
3. 在 `server_handlers/routes/__init__.py` 中注册新路由
4. 在服务层实现具体的业务逻辑

不需要修改 Runtime 或 Core 层的代码，只需要在 Server 层添加 HTTP 接口包装。
