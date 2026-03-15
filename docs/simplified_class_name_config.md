# Agent Profile 配置简化 - 完成

## ✅ 已完成的修改

成功将Agent配置中的`module`和`class_name`两个字段合并为一个`class_name`字段，使用完整的类路径。

### 修改内容

#### 1. AgentLoader (`src/agentmatrix/core/loader.py`)

**修改前**：
```python
# 1. 解析基础类信息
module_name = profile["module"]
class_name = profile["class_name"]

# 清理配置中的特殊字段
del profile["module"]
del profile["class_name"]

# 4. 动态导入 Agent 类
try:
    module = importlib.import_module(module_name)
    agent_class = getattr(module, class_name)
except (ImportError, AttributeError) as e:
    raise ImportError(f"无法加载 Agent 类: {module_name}.{class_name}. 错误: {e}")
```

**修改后**：
```python
# 1. 解析基础类信息（新格式：完整类路径）
class_full_path = profile.get("class_name", "agentmatrix.agents.base.BaseAgent")

# 支持向后兼容：如果存在旧的 module 字段，则合并
if "module" in profile:
    module_name = profile["module"]
    class_name = profile["class_name"]
    class_full_path = f"{module_name}.{class_name}"
    self.logger.warning(f">>> ⚠️  配置文件使用旧格式 (module + class_name)，建议改为单一 class_name: {class_full_path}")
    del profile["module"]
else:
    # 新格式：从完整路径解析 module 和 class
    parts = class_full_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"class_name 格式错误: {class_full_path}，应为 'module.path.ClassName'")
    module_name, class_name = parts

# 清理配置中的特殊字段
if "class_name" in profile:
    del profile["class_name"]

# 4. 动态导入 Agent 类
try:
    module = importlib.import_module(module_name)
    agent_class = getattr(module, class_name)
except (ImportError, AttributeError) as e:
    raise ImportError(f"无法加载 Agent 类: {class_full_path}. 错误: {e}")
```

#### 2. Server API (`server.py`)

**AgentConfigRequest 修改**：
```python
# 修改前
class AgentConfigRequest(BaseModel):
    name: str
    description: str
    module: str = "agentmatrix.agents.base"
    class_name: str = "BaseAgent"
    ...

# 修改后
class AgentConfigRequest(BaseModel):
    name: str
    description: str
    class_name: str = "agentmatrix.agents.base.BaseAgent"  # 新格式：完整类路径
    ...
```

**AgentUpdateRequest 修改**：
```python
# 修改前
class AgentUpdateRequest(BaseModel):
    ...
    module: Optional[str] = None
    class_name: Optional[str] = None
    ...

# 修改后
class AgentUpdateRequest(BaseModel):
    ...
    class_name: Optional[str] = None  # 新格式：完整类路径
    ...
```

**create_agent_profile 修改**：
```python
# 修改前
profile = {
    "name": request.name,
    "description": request.description,
    "module": request.module,
    "class_name": request.class_name,
}

# 修改后
profile = {
    "name": request.name,
    "description": request.description,
    "class_name": request.class_name,  # 新格式：完整类路径
}
```

**update_agent_profile 修改**：
```python
# 删除了 module 字段的处理
# 只保留：
if request.class_name is not None:
    profile["class_name"] = request.class_name
```

#### 3. 配置文件更新

**User.yml (模板)**：
```yaml
# 修改前
name: {{USER_NAME}}
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent
...

# 修改后
name: {{USER_NAME}}
description: Master of world
class_name: agentmatrix.agents.user_proxy.UserProxyAgent
...
```

**Mark.yml**：
```yaml
# 修改前
class_name: BaseAgent
description: 网络情报专家
module: agentmatrix.agents.base
name: Mark
...

# 修改后
name: Mark
description: 网络情报专家
class_name: agentmatrix.agents.base.BaseAgent
...
```

## 新格式说明

### 默认值

- **普通Agent**：`agentmatrix.agents.base.BaseAgent`
- **User Agent**：`agentmatrix.agents.user_proxy.UserProxyAgent`

### 配置示例

**最简配置**：
```yaml
name: MyAgent
description: 我的Agent
# class_name 使用默认值: agentmatrix.agents.base.BaseAgent
```

**完整配置**：
```yaml
name: MyAgent
description: 我的Agent
class_name: agentmatrix.agents.base.BaseAgent
backend_model: default_llm
skills:
  - web_search
  - memory
  - file
persona:
  base: |
    你是一个...
```

## 向后兼容性

✅ **完全向后兼容** - AgentLoader 会自动识别旧格式：

- 如果配置文件中同时存在 `module` 和 `class_name` 字段，会自动合并为完整路径
- 会输出警告日志，提示用户升级到新格式
- 不影响现有Agent的正常加载

## 测试结果

### ✅ 新格式测试
```
=== 测试加载新格式 Agent ===

Loading agent from Mark.yml...
Agent Mark brain set to default_llm
[Mark] Using system default SLM.

Loading agent from User.yml...
Agent DKT brain set to default_llm
[DKT] Using system default SLM.

✅ 成功加载 2 个agents
```

### ✅ 向后兼容性测试
```
=== 测试向后兼容性（旧格式）===

Agent TestAgent brain set to default_llm
[TestAgent] Using system default SLM.

✅ 成功加载旧格式配置
✅ 向后兼容性正常，可以处理旧格式配置
```

## 使用指南

### Web界面创建Agent

1. 打开 "Create Agent" 界面
2. 填写：
   - **Name**: Agent名称
   - **Description**: 描述
   - **Class Name**: `agentmatrix.agents.base.BaseAgent` (默认，可以修改)
3. 选择Skills、配置Persona等
4. 保存后，生成的YAML文件将使用新格式

### 手动创建Agent

**推荐（新格式）**：
```yaml
name: MyAgent
description: 我的Agent
class_name: agentmatrix.agents.base.BaseAgent
skills:
  - web_search
  - memory
```

**不推荐（旧格式，但仍然支持）**：
```yaml
name: MyAgent
description: 我的Agent
module: agentmatrix.agents.base
class_name: BaseAgent
skills:
  - web_search
  - memory
```

## 迁移指南

### 现有Agent升级

如果你有使用旧格式的Agent配置文件：

**选项1：自动兼容（无需操作）**
- AgentLoader会自动识别旧格式
- Agent可以正常加载和使用
- 会在日志中看到警告提示

**选项2：手动升级（推荐）**

将：
```yaml
module: agentmatrix.agents.base
class_name: BaseAgent
```

改为：
```yaml
class_name: agentmatrix.agents.base.BaseAgent
```

## 优势

1. **更简洁** - 减少配置字段
2. **更清晰** - 完整类路径一目了然
3. **更灵活** - 可以轻松指定不同的类路径
4. **向后兼容** - 不影响现有配置

## 文件清单

### 修改的文件
1. ✅ `src/agentmatrix/core/loader.py` - AgentLoader解析逻辑
2. ✅ `server.py` - API请求模型和创建/更新逻辑
3. ✅ `web/matrix_template/.matrix/configs/agents/User.yml` - 模板文件
4. ✅ `examples/MyWorld/.matrix/configs/agents/User.yml` - 示例User agent
5. ✅ `examples/MyWorld/.matrix/configs/agents/Mark.yml` - 示例Base agent

### 测试验证
- ✅ 新格式加载测试通过
- ✅ 向后兼容性测试通过
- ✅ 所有Agent正常加载

---

**状态**: ✅ 完成并测试通过
**日期**: 2025-03-15
