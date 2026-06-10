# 命名统一：namespace → knowledge base (kb)

## 原则

- 用户界面：始终用"知识库"
- 代码变量：`kb` / `kb_name` / `kb_root` / `current_kb`
- API 路径：`/api/knowledge/kbs`
- Agent action：`create_kb`, `list_kbs`
- 内部类名：`KBRegistry`, `KBInstance`（不再用 Namespace）

## 改动清单

### 1. _shared.py（先改，其他文件依赖它）

- `NamespaceInstance` → `KBInstance`
- `NamespaceRegistry` → `KBRegistry`
- `_instances: Dict[str, NamespaceInstance]` → `Dict[str, KBInstance]`
- 返回类型标注更新

### 2. skill.py

- `create_namespace` → `create_kb`
- `list_namespaces` → `list_kbs`
- `_ensure_namespace` → `_ensure_kb`
- 所有 `namespace` 参数 → `kb_name`
- `_current_namespace` → `_current_kb`
- 所有用户可见字符串：`命名空间` → `知识库`
- action 描述更新

### 3. knowledge_base_agent.py

- `_current_namespace` → `_current_kb`
- `NamespaceRegistry` → `KBRegistry`
- 所有注释/文档字符串更新

### 4. wiki_maintenance_service.py

- `NamespaceRegistry` → `KBRegistry`
- `_scan_namespace` → `_scan_kb`
- `namespace` 参数 → `kb_name`
- 日志字符串更新

### 5. knowledge.py（后端 API）

- `/namespaces` → `/kbs`
- `CreateNamespaceRequest` → `CreateKBRequest`
- `NamespaceRegistry` → `KBRegistry`
- 响应字段 `namespaces` → `kbs`

### 6. api/knowledge.js

- `listNamespaces` → `listKBs`
- `createNamespace` → `createKB`
- `getNamespace` → `getKB`
- 所有 API 路径 `/namespaces/` → `/kbs/`

### 7. stores/knowledge.js

- `namespaces` → `kbs`
- `currentNamespace` → `currentKB`
- `fetchNamespaces` → `fetchKBs`
- `selectNamespace` → `selectKB`
- `clearCurrent` 中的变量更新

### 8. Vue 组件

**KnowledgeBaseView.vue**:
- `fetchNamespaces` → `fetchKBs`
- `selectNamespace` → `selectKB`
- `onSelectNamespace` → `onSelectKB`

**KBList.vue**:
- `knowledgeStore.namespaces` → `knowledgeStore.kbs`

**CreateKBWizard.vue**:
- `knowledgeAPI.createNamespace` → `knowledgeAPI.createKB`
- `knowledgeStore.fetchNamespaces` → `knowledgeStore.fetchKBs`
- `knowledgeStore.namespaces` → `knowledgeStore.kbs`
- `knowledgeStore.selectNamespace` → `knowledgeStore.selectKB`

**WikiView.vue**:
- `knowledgeStore.currentNamespace` → `knowledgeStore.currentKB`

**WikiSourceManager.vue**:
- `knowledgeStore.currentNamespace` → `knowledgeStore.currentKB`

**WikiChatPanel.vue**:
- `knowledgeStore.currentNamespace` → `knowledgeStore.currentKB`

### 9. knowledge_base.yml（persona）

- `命名空间` → `知识库`
- `create_namespace` → `create_kb`
- `list_namespaces` → `list_kbs`

### 10. runtime.py

- `NamespaceRegistry` → `KBRegistry`（shutdown_all 调用）

## 实现顺序

1. `_shared.py` — 类重命名
2. `skill.py` — action 重命名 + 参数重命名 + 字符串更新
3. `knowledge_base_agent.py` — 变量重命名
4. `wiki_maintenance_service.py` — 变量重命名
5. `knowledge.py` — API 路径 + 变量重命名
6. `api/knowledge.js` — API 路径 + 方法重命名
7. `stores/knowledge.js` — 变量 + 方法重命名
8. Vue 组件 — 引用更新
9. `knowledge_base.yml` — persona 更新
10. `runtime.py` — import 更新
