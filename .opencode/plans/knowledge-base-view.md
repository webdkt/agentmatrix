# KnowledgeBaseView Implementation Plan

## Overview

Add a KnowledgeBaseView to agentmatrix-desktop for managing knowledge bases (wiki namespaces).

## User Flow

```
1. 打开 KnowledgeBaseView → 看到命名空间列表（可能为空）
2. 点击"添加" → 进入创建向导
3. 输入 name + description → 点击"生成 Schema"
4. 后端生成 schema 文本返回（不创建任何东西）
5. 用户 review/编辑 schema → 点击"创建"
6. 后端创建 namespace + 保存 schema
7. 进入 Wiki 界面
```

## 后端 API

### 端点设计

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/knowledge/namespaces` | 列出命名空间 |
| POST | `/api/knowledge/namespaces/generate-schema` | 预览：生成 schema 文本（无副作用） |
| POST | `/api/knowledge/namespaces` | 创建：namespace + schema（原子操作） |
| GET | `/api/knowledge/namespaces/{name}` | 命名空间详情 |
| PUT | `/api/knowledge/namespaces/{name}/schema` | 更新 schema |
| GET | `/api/knowledge/namespaces/{name}/pages` | 列出页面 |
| GET | `/api/knowledge/namespaces/{name}/pages/{path:path}` | 页面内容 |
| GET | `/api/knowledge/namespaces/{name}/sources` | 列出源目录 |
| POST | `/api/knowledge/namespaces/{name}/sources` | 注册源目录 |
| DELETE | `/api/knowledge/namespaces/{name}/sources/{id}` | 删除源目录 |

### 后端文件

```
server_handlers/
├── routes/knowledge.py    # 新增
├── models.py              # 新增请求模型
└── routes/__init__.py     # 注册路由
```

### 关键实现

**generate-schema 端点**：
- 从 runtime 获取 KnowledgeBaseAgent 的 brain
- 调用 `brain.think_with_retry(SCHEMA_GENERATION_PROMPT)` 生成 schema
- 返回 schema 文本

**create namespace 端点**：
- 接收 name + description + schema
- 调用 `NamespaceRegistry.get_or_create()` 创建目录和 DB
- 调用 `wiki_manager.init_with_schema(schema)` 保存 schema
- 返回创建结果

**list pages 端点**：
- `WikiManager.list_page_files()` 获取文件列表
- `KnowledgeDB.get_all_pages()` 获取 DB 元数据
- 合并返回

## 前端

### 文件结构

```
src/
├── api/knowledge.js                    # API 层
├── stores/knowledge.js                 # Pinia 状态管理
└── components/knowledge/
    ├── KnowledgeBaseView.vue           # 主视图容器
    ├── KBList.vue                      # 命名空间列表 + 添加按钮
    ├── CreateKBWizard.vue              # 创建向导（3步）
    ├── WikiView.vue                    # Wiki 界面
    ├── WikiSidebar.vue                 # 左侧面板（2 tab）
    ├── WikiPageTree.vue                # Tab 1: 目录树
    ├── WikiSourceManager.vue           # Tab 2: 源目录管理
    ├── WikiPageViewer.vue              # 右侧页面查看器
    └── WikiChatPanel.vue               # 右侧浮动聊天面板
```

### 视图注册

**ViewSelector.vue**：添加 `{ id: 'knowledge', icon: 'book', label: 'views.knowledge.title' }`

**ViewContainer.vue**：添加 `v-else-if="currentView === 'knowledge'"`

### 组件设计

**KnowledgeBaseView.vue**：
- 状态：`list` → `wizard` → `wiki`
- 无命名空间时自动进入 wizard

**KBList.vue**：
- `GET /api/knowledge/namespaces` 获取列表
- 每项：名称、schema 状态、页面数
- 点击 → 进入 WikiView
- "添加" → 进入 wizard

**CreateKBWizard.vue**：
- Step 1: name + description，点击"生成 Schema"
- Step 2: 等待 `POST /api/knowledge/namespaces/generate-schema`，显示 Markdown 编辑器
- Step 3: 用户确认，调用 `POST /api/knowledge/namespaces` 创建

**WikiView.vue**：
- 左侧 WikiSidebar + 右侧 WikiPageViewer + 浮动 WikiChatPanel

**WikiSidebar.vue**：
- 两个 tab：目录树、源管理

**WikiPageTree.vue**：
- `GET /api/knowledge/namespaces/{name}/pages`
- 树形结构，点击加载页面内容

**WikiSourceManager.vue**：
- `GET /api/knowledge/namespaces/{name}/sources`
- 添加：输入路径 + 描述
- 删除：确认后删除

**WikiPageViewer.vue**：
- `GET /api/knowledge/namespaces/{name}/pages/{path}`
- Markdown 渲染（marked 库）
- 只读

**WikiChatPanel.vue**：
- 浮动面板，可展开/收起
- 复用 session/email 系统与 KnowledgeBaseAgent 对话

### 实现顺序

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | 后端路由 + 模型 | `knowledge.py`, `models.py`, `__init__.py` |
| 2 | 前端 API | `api/knowledge.js` |
| 3 | 前端 store | `stores/knowledge.js` |
| 4 | 视图注册 | `ViewSelector.vue`, `ViewContainer.vue` |
| 5 | 主容器 | `KnowledgeBaseView.vue` |
| 6 | 命名空间列表 | `KBList.vue` |
| 7 | 创建向导 | `CreateKBWizard.vue` |
| 8 | Wiki 容器 | `WikiView.vue`, `WikiSidebar.vue` |
| 9 | 目录树 | `WikiPageTree.vue` |
| 10 | 源管理 | `WikiSourceManager.vue` |
| 11 | 页面查看器 | `WikiPageViewer.vue` |
| 12 | 聊天面板 | `WikiChatPanel.vue` |
| 13 | i18n | `locales/*.json` |
