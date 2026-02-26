# AgentMatrix Web 应用

AgentMatrix Web 应用是基于 AgentMatrix 框架的官方 Web 管理界面，提供可视化的 Agent 交互和管理功能。

## 🌟 特性

- 📧 **邮件式交互界面** - 直观的自然语言通信体验
- 🎨 **现代化 UI** - 基于 Tailwind CSS 的精美界面
- 🔄 **实时通信** - WebSocket 支持的实时消息更新
- 📊 **会话管理** - 可视化会话历史和状态
- 🤖 **多 Agent 协作** - 轻松管理多个 Agent 的协作
- 🔍 **日志监控** - 实时查看 Agent 思考和执行过程

## 🚀 快速开始

### 1. 安装依赖

```bash
# 确保已安装 AgentMatrix 核心框架
pip install -e .

# 或从源码安装
cd /path/to/agentmatrix
pip install -e .
```

### 2. 启动 Web 服务器

```bash
# 使用默认配置
python server.py

# 指定 World 目录
python server.py --matrix-world ./MyWorld

# 自定义主机和端口
python server.py --host 0.0.0.0 --port 8080

# 指定后端模型
python server.py --backend-model gpt-4 --cerebellum-model gpt-3.5-turbo
```

### 3. 访问 Web 界面

打开浏览器访问:
```
http://localhost:8000
```

## 📁 目录结构

```
web/
├── index.html           # 主界面（单页应用）
├── css/                 # 自定义样式
│   └── custom.css      # 自定义 CSS 覆盖
├── js/                  # JavaScript 模块
│   ├── app.js          # 主应用逻辑
│   └── ...
├── libs/               # 第三方库
│   └── marked.min.js   # Markdown 渲染
└── matrix_template/    # 配置模板
    ├── agents/         # Agent 配置模板
    └── workspace/      # 工作区模板
```

## 🎛️ 功能说明

### 邮件式交互

Web 应用模拟了邮件客户端的界面，让你通过自然语言与 Agent 交互：

1. **发送邮件** - 点击"新建邮件"，填写收件人（Agent 名称）、主题和内容
2. **查看回复** - Agent 的回复会以邮件形式返回
3. **会话线程** - 相关邮件会自动组织成线程
4. **多会话管理** - 可以同时与多个 Agent 进行对话

### Agent 管理

- 📋 **查看 Agent 列表** - 浏览所有可用的 Agent
- 🔍 **Agent 详情** - 查看 Agent 的配置、技能和描述
- ⚙️ **创建 Agent** - 通过向导创建新的 Agent 配置
- 🎭 **角色切换** - 为不同任务选择合适的 Agent

### 实时监控

- 📊 **执行日志** - 查看 Agent 的思考过程和执行步骤
- 🔄 **状态更新** - 实时显示任务状态
- 📈 **性能指标** - 监控响应时间和资源使用

## 🔧 配置说明

### 环境变量

创建 `.env` 文件或设置环境变量：

```bash
# OpenAI API 配置
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1  # 可选

# Anthropic API 配置（如果使用 Claude）
ANTHROPIC_API_KEY=sk-ant-xxx

# 其他配置
MATRIX_WORLD=./MyWorld      # World 目录路径
BACKEND_MODEL=gpt-4         # 后端模型
CEREBELLUM_MODEL=gpt-3.5-turbo  # 小脑模型
```

### server.py 参数

```bash
--matrix-world    # World 目录路径（默认: ./MatrixWorld）
--host            # 绑定主机（默认: 127.0.0.1）
--port            # 绑定端口（默认: 8000）
--backend-model   # 后端 LLM 模型（默认: gpt-4）
--cerebellum-model # 小脑模型（默认: gpt-3.5-turbo）
```

## 🎨 界面定制

### 修改主题

Web 应用使用 Tailwind CSS，可以在 `index.html` 中修改主题配置：

```html
<script>
tailwind.config = {
  theme: {
    extend: {
      colors: {
        primary: { /* 主色调 */ },
        accent: { /* 强调色 */ },
        // ...
      }
    }
  }
}
</script>
```

### 自定义样式

编辑 `web/css/custom.css` 来自定义界面样式。

## 🔄 API 接口

Web 应用通过 WebSocket 和 REST API 与后端通信：

### WebSocket 连接

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // 处理消息
};
```

### REST API

- `POST /api/emails` - 发送邮件
- `GET /api/emails` - 获取邮件列表
- `GET /api/agents` - 获取 Agent 列表
- `GET /api/sessions` - 获取会话列表

详细 API 文档请访问: `http://localhost:8000/docs`

## 🐛 常见问题

### 无法连接到服务器

1. 检查服务器是否正在运行
2. 确认防火墙设置
3. 检查主机和端口配置

### Agent 无响应

1. 查看服务器终端日志
2. 确认 API 密钥已正确设置
3. 检查后端模型配置

### 邮件发送失败

1. 确认收件人 Agent 名称正确
2. 检查 Agent 配置文件
3. 查看浏览器控制台错误信息

## 📚 更多资源

- [AgentMatrix 核心框架文档](../docs/)
- [示例和教程](../examples/)
- [架构设计文档](../docs/agent-and-micro-agent-design.md)

## 🚧 开发说明

### 本地开发

```bash
# 启动开发服务器（热重载）
python main.py

# 或使用 uvicorn
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

### 前端开发

前端是一个单页应用（SPA），主要技术栈：
- **Alpine.js** - 轻量级响应式框架
- **Tailwind CSS** - 实用优先的 CSS 框架
- **Marked.js** - Markdown 渲染
- **Tabler Icons** - 图标库

### 调试

1. 打开浏览器开发者工具（F12）
2. 查看 Console 标签获取错误信息
3. 使用 Network 标签监控 API 调用
4. 查看 WebSocket 连接状态

## 🤝 贡献

欢迎贡献！如果你有改进建议或发现 Bug：

1. 创建 Issue 描述问题
2. Fork 项目并创建分支
3. 提交 Pull Request

我们特别欢迎：
- 🎨 UI/UX 改进
- 🔧 功能增强
- 📱 响应式设计优化
- ♿ 无障碍访问支持

## 📝 许可证

Apache License 2.0 - 详见项目根目录的 LICENSE 文件
