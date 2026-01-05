# AgentMatrix UI 开发规范

> **版本**: 1.0
> **更新日期**: 2026-01-05

## 1. 项目定位

AgentMatrix 支持两种使用模式：

### 1.1 作为 Python 库
- 通过 `pip install matrix-for-agents` 安装
- 用户在自己的项目中 `import agentmatrix` 使用
- 不包含管理界面，只提供核心 Python 代码

### 1.2 作为完整应用
- 克隆完整仓库运行
- 启动 `server.py` 提供 Web 服务
- 包含完整的管理界面，提供图形化的 Agent 管理、监控和配置功能

---

## 2. 目录结构

### 2.1 目录组织原则

- **src/agentmatrix/**：纯 Python 包代码
- **web/**：前端资源，与 src 并列放置
- **目的**：库模式打包时不包含 web/，应用模式运行时包含完整界面


---

## 3. 技术栈

### 3.1 前端技术

- **Alpine.js**：响应式框架，CDN 引入，无需构建工具
- **Tailwind CSS**：实用优先的 CSS 框架，CDN 引入
- **Tabler Icons**：图标库
- **Chart.js**：数据可视化图表（如需要）

### 3.2 后端技术

- **FastAPI**：Web 框架，提供 API 和自动文档
- **WebSockets**：实时双向通信
- **StaticFiles**：静态文件服务（FastAPI 内置）

---

## 4. 静态资源管理

### 4.1 文件组织

#### CSS
- 优先使用 Tailwind CSS 类名
- 自定义样式放在 `web/css/custom.css`

#### JavaScript
- 通用工具放在 `web/js/app.js`
- API 调用封装放在 `web/js/api.js`
- WebSocket 客户端放在 `web/js/ws.js`

### 4.2 HTML 模板结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- 1. Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- 2. Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    <!-- 3. 图标库 -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">

    <!-- 4. 自定义样式和 JS -->
    <link rel="stylesheet" href="/css/custom.css">
    <script src="/js/app.js"></script>
</head>
<body>
    <!-- 页面内容 -->
</body>
</html>
```

### 4.3 静态文件服务配置

```python
# server.py
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
import os

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
```

---

## 5. 页面设计原则

### 5.1 布局

- 侧边栏导航 + 主内容区
- 响应式设计，适配不同屏幕尺寸
- 使用 Flexbox 布局

### 5.2 颜色规范

- 主色：`slate`
- 强调色：`blue`
- 成功：`green`
- 警告：`yellow`
- 错误：`red`

### 5.3 组件样式

使用 Tailwind CSS 类名构建组件：
- 卡片：`bg-white rounded-lg shadow p-6`
- 主按钮：`px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700`
- 表格：Tailwind 的 divide-y 和表格工具类

---

## 6. API 设计规范

### 6.1 RESTful API

- 使用 REST 风格的 API 端点
- 统一的响应格式
- 清晰的错误处理

### 6.2 WebSocket

- 用于实时更新和推送
- JSON 格式的消息
- 事件类型的统一命名

### 6.3 数据格式

#### 成功响应
```json
{
  "success": true,
  "data": {...}
}
```

#### 错误响应
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

---

## 7. 开发模式

### 7.1 本地开发

```bash
# 启动服务
python server.py

# 浏览器访问
open http://localhost:8000
```

### 7.2 热重载

- 后端：使用 Uvicorn 的 `--reload` 选项
- 前端：直接刷新浏览器

### 7.3 浏览器支持

- Chrome/Edge：最新 2 个版本
- Firefox：最新 2 个版本
- Safari：最新 2 个版本

---

## 8. 打包和分发

### 8.1 库模式

```toml
# pyproject.toml
[tool.setuptools.packages.find]
where = ["src"]
```

打包时不包含 web/ 目录，只包含 Python 源代码。

### 8.2 应用模式

完整运行时包含 web/ 目录，可通过以下方式分发：
- Docker 容器
- 直接克隆仓库
- PyInstaller 打包（可选）

---

## 9. 代码规范

### 9.1 前端

- 使用 Alpine.js 进行状态管理
- 封装 API 调用，避免直接使用 fetch
- 组件函数保持简单，复杂逻辑移到后端

### 9.2 后端

- API 路由模块化，按功能划分文件
- 使用 FastAPI 的 HTTPException 进行错误处理
- 所有端点添加类型提示和文档字符串

### 9.3 性能优化

- 前端：使用 WebSocket 实时更新，避免轮询
- 前端：列表数据分页加载
- 后端：使用 async/await 异步处理
- 后端：优化数据库查询

---

## 10. 文档

### 10.1 API 文档

FastAPI 自动生成：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

确保所有端点都有类型提示和文档字符串。

### 10.2 代码注释

- 后端：使用 docstring 说明函数功能、参数、返回值
- 前端：使用 HTML 注释说明复杂结构

---

## 11. 安全

- 当前：开发阶段，本地运行，无需认证
- 未来：可添加密码保护、API 密钥认证、输入验证

---

## 12. 参考资源

### 技术文档
- [Alpine.js](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [FastAPI](https://fastapi.tiangolo.com/)

### 设计参考
- [Tailwind UI](https://tailwindui.com/components)
- [Tabler Icons](https://tabler-icons.io/)
- [Chart.js](https://www.chartjs.org/docs/latest/samples/)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0  | 2026-01-05 | 初始版本，定义 UI 开发框架 |
