# Desktop App 前端架构

AgentMatrix Desktop 的前端基于 Tauri + Vue 3 构建。Tauri 提供 Rust 编写的桌面运行时（窗口管理、系统集成），Vue 3 提供用户界面。

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 桌面框架 | Tauri (Rust) | 窗口管理、菜单、系统托盘、文件系统访问 |
| 前端框架 | Vue 3 + Vite | 用户界面、组件化开发 |
| 状态管理 | Pinia | 全局状态（Agent、Session、Email、UI） |
| 网络通信 | Fetch API + WebSocket | HTTP 请求和实时事件 |
| 国际化 | Vue I18n | 中英文切换 |

---

## 前后端通信

前端与 FastAPI 后端之间使用两种通信方式：

### HTTP API

用于请求-响应式的操作：
- 发送邮件
- 查询会话列表
- 获取 Agent 配置
- 修改系统设置

### WebSocket

用于实时事件推送：
- Agent 状态变化
- 新邮件到达
- 执行进度更新
- 系统通知

前端在启动时建立 WebSocket 连接，后端通过该连接推送所有实时事件。前端不需要轮询，所有状态更新都是推送的。

---

## 状态管理

使用 Pinia 按功能域划分 Store：

| Store | 职责 |
|-------|------|
| Agent Store | Agent 列表、状态、配置 |
| Session Store | 会话列表、当前会话、邮件历史 |
| Email Store | 邮件草稿、发送状态、附件 |
| UI Store | 界面状态（侧边栏展开、主题、语言） |
| Settings Store | 系统设置、LLM 配置、代理配置 |

Store 之间通过订阅和事件进行协作。例如，当 WebSocket 收到「新邮件」事件时，Session Store 更新会话列表，Agent Store 更新未读计数，UI Store 可能触发通知。

---

## 模块划分

前端代码按功能模块组织：

### 组件层

按功能域分组的 Vue 组件：

- **email**：邮件列表、邮件项、邮件回复、附件显示
- **session**：会话列表、会话项、会话详情
- **agent**：Agent 列表、Agent 状态指示器、Agent 详情
- **settings**：设置面板、LLM 配置、代理配置、邮件代理配置
- **wizard**：冷启动向导的各个步骤
- **dialog**：各种对话框和弹窗

### API 层

按功能域封装的 HTTP 请求函数：

- agentAPI：Agent 相关的增删改查
- sessionAPI：会话和邮件的查询、发送
- configAPI：系统配置的读写
- skillAPI：技能列表查询

### 组合式函数

复用的逻辑封装为 Vue Composables：

- 使用 WebSocket
- 拖拽上传附件
- 分页加载
- 表单验证

---

## 国际化

界面支持中英文切换。翻译文件存放在 `src/i18n/locales/` 目录下，按语言代码命名（`zh.json`、`en.json`）。

切换语言时：
1. 用户在前端设置中选择语言
2. Vue I18n 加载对应的翻译文件
3. 界面文字即时更新
4. 语言偏好保存到本地存储，下次启动自动恢复

---

## 实时状态推送

前端通过 WebSocket 订阅后端事件。事件类型包括：

- **Agent 状态变化**：更新 Agent 列表中的状态显示
- **Think 事件**：显示 Agent 的思考内容
- **Action 事件**：显示正在执行的动作名称
- **Result 事件**：显示动作执行结果
- **Question 事件**：弹出对话框等待用户输入
- **Complete 事件**：任务完成，更新会话

这些事件被路由到对应的 Store，Store 更新状态后触发 Vue 的响应式更新，界面自动刷新。

---

## 构建与打包

开发时使用 Vite 的开发服务器，通过 Tauri 的 dev 命令启动：

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

生产构建会生成桌面应用的可执行文件：

```bash
npm run tauri:build
```

构建产物根据平台不同，生成 `.app`（macOS）、`.exe`（Windows）或 `.AppImage`/`.deb`（Linux）。

---

## 扩展前端

如果你需要修改或扩展前端功能：

1. 在 `src/components/` 下添加新组件或修改现有组件
2. 在 `src/stores/` 下添加新的 Pinia Store 或扩展现有 Store
3. 在 `src/api/` 下添加新的 API 封装
4. 在 `src/i18n/locales/` 下添加翻译文本

前端与后端的接口通过 HTTP API 和 WebSocket 事件定义，修改前端通常不需要修改后端，除非需要新的 API 端点。
