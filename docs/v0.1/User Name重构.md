# User Agent 名称重构可行性研究

## 📋 需求动机

### 当前问题
在 AgentMatrix 系统中，"User" agent 作为一个特殊的代理角色，其名字被硬编码为 "User"。这带来诸多限制。

### 目标
允许用户自定义 User agent 的名字，同时：
- ✅ 保持其在系统中的特殊代理角色
- ✅ 不破坏现有功能
- ✅ 提供清晰的配置方式

---

## 🔍 当前架构分析

### User Agent 的定义和加载

#### 1. 配置文件定义

**位置**: `src/agentmatrix/profiles/user_proxy.yml`

```yaml
#You should always have one USER agent
name: User
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent
```

User agent 通过 YAML 配置文件定义，包含：
- **Name**: "User"（硬编码）
- **Module**: `agentmatrix.agents.user_proxy`
- **Class**: `UserProxyAgent`
- **Mixins**: FileSkillMixin（提供文件系统操作能力）

#### 2. 加载机制

**核心文件**: `src/agentmatrix/core/loader.py`

`AgentLoader` 类负责加载所有 agent：
- **第 179-187 行**：`load_all()` 方法遍历配置路径下的所有 `.yml` 文件
- 使用 Python 的 `importlib` 动态导入
- 将每个 agent 以其 `name` 为键存储在字典中
- **加载过程中对 User agent 没有特殊处理** - 它和其他 agent 一样被加载

**Runtime 集成**: `src/agentmatrix/core/runtime.py`

- **第 85-88 行**：实例化 `AgentLoader` 并加载所有 agent
- **第 89-90 行**：为所有 agent（包括 User）附加异步事件回调
- **第 176-182 行**：从快照恢复 agent 状态（如果存在）
- **第 189-196 行**：向 PostOffice 注册所有 agent

#### 3. User Agent 实现

**文件**: `src/agentmatrix/agents/user_proxy.py`

`UserProxyAgent` 类继承自 `BaseAgent`，具有特殊功能：

```python
class UserProxyAgent(BaseAgent):
    def __init__(self, name, description, config):
        super().__init__(name, description, config)
        self.on_mail_received = None  # 第13行：回调属性

    def set_mail_handler(self, handler):  # 第16-18行
        """设置邮件处理器回调"""
        self.on_mail_received = handler

    def process_email(self, email):  # 第20-42行
        """处理来自其他 agent 的邮件"""
        if self.on_mail_received:
            self.on_mail_received(email)

    def speak(self, user_session_id, target, content, subject=None):  # 第43-81行
        """代表用户发送邮件"""
        # 发送邮件实现...
```

---

## 📍 硬编码 "User" 的全部位置

### Python 代码引用

#### **server.py**（Web 服务器）
- **第 187 行**: `if "User" in matrix_runtime.agents:` - 检查 User agent 是否存在
- **第 221 行**: `matrix_runtime.agents["User"].set_mail_handler(user_mail_callback)` - 设置邮件处理器
- **第 397 行**: `user_agent = matrix_runtime.agents.get("User")` - 获取 User agent 用于发送邮件

#### **cli_runner.py**（命令行接口）
- **第 35 行**: `matrix.agents["User"].on_mail_received = print_to_console` - 设置控制台输出回调
- **第 73 行**: `await matrix.agents["User"].speak(...)` - 通过 User agent 发送邮件
- **第 86 行**: `await matrix.agents["User"].speak(user_session_id, target.strip(), content.strip())` - 发送消息

#### **database.py**（数据库操作）
- **第 88 行**: `WHERE user_session_id = ? AND (sender = 'User' OR recipient = 'User')` - 过滤 User 相关邮件

#### **post_office.py**（邮件路由）
- **第 235 行**: `email.is_from_user = (email.sender == 'User')` - 标记来自 User 的邮件

#### **base.py**（Agent 基类）
- **第 446 行**: `"to": "收件人 (e.g. 'User', 'Planner', 'Coder')"` - 文档示例

### JavaScript/Web 前端引用

#### **Web 界面** (`web/js/app.js`)
- **第 79 行**: `const filtered = rawAgents.filter(a => a !== 'User')` - 从 agent 列表过滤 User
- **第 202 行**: `if (name === 'User') return 'U'` - 为 User 显示特殊头像
- **第 223-226 行**: 注释引用 `user_proxy` 自动生成主题

#### **客户端 HTML** (`client.html`)
- **第 161 行**: `addLog("LOG", "User", "Task Submitted: " + task)` - 记录 User 操作

### 模板/配置引用

#### **Prompt 模板** (`profiles/prompts/base.txt` 和 `web/matrix_template/agents/prompts/base.txt`)
- **第 82 行**: `[ACTION SIGNAL]: The recipient is 'User'.` - Prompt 示例

#### **User 配置文件**
- `src/agentmatrix/profiles/user_proxy.yml` - 第 2 行: `name: User`
- `web/matrix_template/agents/User.yml` - 第 2 行: `name: User`
- `MyWorld/agents/User.yml` - 第 2 行: `name: User`

### 文档引用

#### **API 文档** (`docs/dev-plan/phase1-api.md`)
- **第 207, 220, 265 行**: 示例 JSON 显示 `"sender": "User"` 和 `"recipient": "User"`
- **第 551 行**: SQL 过滤注释: `# 过滤条件: from='User' OR to='User'`

---

## 🎯 User Agent 的特殊性分析

### 独特功能

User agent 有几个区别于其他 agent 的特征：

#### **1. 外部接口代理**
- 充当人类用户与 agent 系统之间的接口
- 拥有 `on_mail_received` 回调，外部代码可以设置
- 其他 agent **没有**这个回调机制

#### **2. 邮件处理器模式**
- **Server**: 使用 `set_mail_handler()` 将接收到的邮件推送到 WebSocket 客户端
- **CLI**: 使用 `on_mail_received` 将邮件打印到控制台
- 其他 agent 通过 `process_email()` 内部处理邮件

#### **3. UI 中的特殊过滤**
- Web 界面从 agent 列表过滤 "User"（app.js 第 79 行）
- User 获得特殊的头像显示（单字母 "U" 而非 2 字母）
- 对话历史是 "User 视角"（来自 User 的消息在左侧，其他在右侧）

#### **4. 数据库查询**
- 特殊 SQL 查询过滤 `sender = 'User' OR recipient = 'User'`
- `get_session_emails_for_user()` 专门检索 User 相关邮件
- 基于与 "User" 字符串的比较添加 `is_from_user` 标志

#### **5. 会话管理**
- User 会话与 agent 操作分开跟踪
- 每个对话有 `user_session_id`，链接到 User agent
- 会话在 `user_sessions.json` 中管理

### 关键发现

**⚠️ 重要**: 没有**基于类型的特殊处理**。没有类型检查或接口实现来区分 User agent 和其他 agent。特殊处理完全基于**字符串名称 "User"** 在整个代码库中被硬编码。

---

## 💡 实现方案

### 方案选择：冷启动时交互式配置

**设计原则**：
- ❌ **不需要向后兼容** - 这是一个架构性变更
- ❌ **不需要数据迁移** - 新建的 Matrix World 直接使用新名称
- ✅ **必须配置** - 冷启动时强制用户输入 User agent 名称
- ✅ **配置持久化** - 名称存储在配置文件中，运行时读取

**核心思路**：
1. 冷启动时通过 Web wizard 或 CLI 交互式收集用户名
2. 创建 `matrix_world.yml` 配置文件存储用户名
3. 模板复制时动态替换 `User.yml` 中的 `{{USER_NAME}}` 占位符，修改base.txt里的例子
4. 运行时从配置文件读取并验证用户名
---

## 🎯 推荐方案：配置化设计

### 架构设计

```
┌─────────────────────────────────────────┐
│  冷启动配置层 (Cold Start Config)        │
│  ┌────────────────────────────────────┐ │
│  │ Web Wizard / CLI Interactive      │ │
│  │ 收集: user_agent_name             │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  配置文件层 (Config Files)              │
│  ┌────────────────────────────────────┐ │
│  │ matrix_world.yml                  │ │
│  │   user_agent_name: "Alice"        │ │
│  │ User.yml (动态替换)               │ │
│  │   name: {{USER_NAME}} → "Alice"   │ │
│  │ base.txt (动态替换)               │ │
│  │   name: {{USER_NAME}} → "Alice"   │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  运行时层 (Runtime Layer)               │
│  ┌────────────────────────────────────┐ │
│  │ Runtime.USER_AGENT_NAME (常量)    │ │
│  │ 从 matrix_world.yml 读取          │ │
│  │ 使用者: Server, CLI, PostOffice   │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  验证层 (Validation)                    │
│  ┌────────────────────────────────────┐ │
│  │ AgentLoader 验证:                 │ │
│  │ - 必须存在 user proxy agent      │ │
│  │ - 名称必须匹配配置                │ │
│  │ - 否则报错退出                    │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│  表现层 (Presentation Layer)            │
│  ┌────────────────────────────────────┐ │
│  │ 前端从 /api/config 读取           │ │
│  │ 动态过滤/排序                     │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## 🚀 冷启动交互流程设计

### Web Wizard 流程

```
用户启动服务器
    ↓
检测: llm_config.json 不存在？
    ↓ 是
显示 Web Wizard (Step 1/3)
    ├─ 输入: User Agent 名称 ✨ 新增
    │  例如: Alice, Human, 用户
    └─ 验证: 非空、字母数字、长度限制
    ↓
显示 Web Wizard (Step 2/3)
    └─ 输入: LLM 配置（现有流程）
    ↓
显示 Web Wizard (Step 3/3)
    └─ 确认并创建 Matrix World
    ↓
后端处理:
    ├─ 1. 读取 user_agent_name
    ├─ 2. 创建 matrix_world.yml
    │     写入 user_agent_name
    ├─ 3. 复制模板目录
    │     └─ 动态替换 User.yml 和 base.txt:
    │         {{USER_NAME}} → 用户输入的名字
    ├─ 4. 创建 llm_config.json
    └─ 5. 初始化 AgentMatrix Runtime
    ↓
完成: 进入主界面
```

### CLI 交互流程

```
用户运行 CLI
    ↓
检测: matrix_world 不存在？
    ↓ 是
交互式提示:
    🔷 冷启动: 创建新的 Matrix World
    请输入 User Agent 的名称: [Alice] _
    (或使用 --user-name 参数跳过交互)
    ↓
验证输入
    ↓
创建配置:
    ├─ 1. 创建 matrix_world.yml
    ├─ 2. 复制并替换模板
    └─ 3. 提示配置 LLM
    ↓
继续: 正常运行
```

### 配置文件结构

**文件**: `<matrix_world>/matrix_world.yml`

```yaml
# AgentMatrix World Configuration
# 此文件在冷启动时自动创建

# User Agent 配置
user_agent_name: "Alice"  # 用户自定义的 User agent 名称

# 可扩展: 未来可以添加更多配置
# world_name: "MyWorld"
# description: "My custom matrix world"
# created_at: "2025-01-06"
```

**文件**: `<matrix_world>/agents/User.yml` (冷启动后生成)

```yaml
#You should always have one USER agent
name: Alice  # 从 {{USER_NAME}} 替换而来
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent

# 动态 Mixin 组合
mixins:
  - skills.filesystem.FileSkillMixin

# 属性初始化
attribute_initializations:
  on_mail_received: null

instruction_to_caller: "要精炼不要啰嗦"
system_prompt: ""
backend_model: default_llm
```

---

## 🔧 模板变量替换机制

### 模板文件修改

**文件**: `web/matrix_template/agents/User.yml` (模板)

```yaml
#You should always have one USER agent
name: {{USER_NAME}}  # 模板变量
description: Master of world
module: agentmatrix.agents.user_proxy
class_name: UserProxyAgent
```

### 替换逻辑实现

**位置**: `server.py` - `create_directory_structure()` 函数

```python
def create_directory_structure(matrix_world_dir: Path, user_name: str):
    """创建 Matrix World 目录结构并复制模板"""
    import shutil

    template_dir = Path(__file__).resolve().parent / "web" / "matrix_template"
    if not template_dir.exists():
        raise FileNotFoundError(f"Matrix template directory not found: {template_dir}")

    # 创建根目录
    matrix_world_dir.mkdir(parents=True, exist_ok=True)

    # 复制模板目录
    shutil.copytree(template_dir, matrix_world_dir, dirs_exist_ok=True)

    # 🔥 动态替换 User.yml 中的 {{USER_NAME}}
    user_yml_path = matrix_world_dir / "agents" / "User.yml"
    if user_yml_path.exists():
        with open(user_yml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 替换模板变量
        content = content.replace('{{USER_NAME}}', user_name)

        with open(user_yml_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ User agent configured with name: {user_name}")
    #同样逻辑替换 base.txt
```

### 配置文件创建

**位置**: `server.py` - 冷启动处理

```python
def create_world_config(matrix_world_dir: Path, user_name: str):
    """创建 matrix_world.yml 配置文件"""
    config = {
        "user_agent_name": user_name
    }

    config_path = matrix_world_dir / "matrix_world.yml"
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"✅ Created world configuration: {config_path}")
```

---

## 📋 详细实施计划

### 第一阶段：冷启动基础设施

#### 1.1 修改模板文件
- **文件**: `web/matrix_template/agents/User.yml`
  - 将 `name: User` 改为 `name: {{USER_NAME}}`
- **文件**: `web/matrix_template/agents/prompts/base.txt`
  - 将 `User`(开头大写) 改为 `{{USER_NAME}}`

#### 1.2 更新 server.py - 配置创建
- **文件**: `server.py`
  - 修改 `create_directory_structure()` 函数签名：添加 `user_name: str` 参数
  - 添加 `create_world_config()` 函数：创建 `matrix_world.yml`
  - 实现模板变量替换逻辑：`{{USER_NAME}}` → 实际名称
  - 修改冷启动检测：调用时传入 user_name

**代码变更**:
```python
# 修改前
def create_directory_structure(matrix_world_dir: Path):

# 修改后
def create_directory_structure(matrix_world_dir: Path, user_name: str):
    # ... 复制模板
    # ... 替换 {{USER_NAME}}
    # ... 创建 matrix_world.yml
```

#### 1.3 添加配置加载
- **文件**: `server.py`
  - 添加 `load_world_config()` 函数：读取 `matrix_world.yml`
  - 修改初始化流程：加载配置并传递给 Runtime

**更改**: 2 个文件，约 60 行代码

---

### 第二阶段：Web Wizard 改造

#### 2.1 扩展 Wizard UI
- **文件**: `web/wizard.html`
  - 在 Step 1 前添加新的 Step 1: User Agent 名称输入
  - 原有步骤变为 Step 2 和 Step 3
  - 添加输入验证（非空、长度限制、字符限制）
  - 更新进度条为 3 步

**UI 组件**:
```html
<!-- Step 1: User Agent Configuration -->
<div class="wizard-step" data-step="1">
    <h2>👤 配置 User Agent</h2>
    <p>请输入您的 User Agent 的名称（这是您在系统中的代表）</p>
    <input type="text" id="userName" placeholder="例如: Alice, Human, 用户" required>
    <div class="validation-msg"></div>
</div>
```

#### 2.2 更新 API 端点
- **文件**: `server.py`
  - 修改 `POST /api/config/llm` 端点：接收 `user_name` 参数
  - 或创建新的 `POST /api/config/user` 端点

**API 变更**:
```python
@app.post("/api/config/complete")
async def complete_cold_start(config: ColdStartConfig):
    # config.user_name
    # config.llm_configs
    create_directory_structure(..., user_name=config.user_name)
    save_llm_configs(...)
```

#### 2.3 更新前端 JavaScript
- **文件**: `web/js/app.js` 或 `web/js/wizard.js`
  - 添加 User 名称收集逻辑
  - 更新 API 调用以包含 user_name
  - 添加前端验证

**更改**: 3 个文件，约 100 行代码（HTML + JS + API）

---

### 第三阶段：Runtime 和配置管理

#### 3.1 更新 Runtime
- **文件**: `src/agentmatrix/core/runtime.py`
  - 在 `__init__` 中添加 `user_agent_name` 参数
  - 存储为 `self.user_agent_name`（常量）
  - 添加属性 getter: `get_user_agent_name()`

**代码变更**:
```python
class AgentMatrixRuntime:
    def __init__(self, ..., user_agent_name: str):
        self.user_agent_name = user_agent_name
        self.agents = loader.load_all()

    def get_user_agent_name(self) -> str:
        return self.user_agent_name
```

#### 3.2 更新所有硬编码引用
- **文件**: `server.py`
  - 第 187, 221, 397 行：用 `matrix_runtime.get_user_agent_name()` 替换 "User"

- **文件**: `cli_runner.py`
  - 第 35, 73, 86 行：用 `matrix.get_user_agent_name()` 替换 "User"

- **文件**: `src/agentmatrix/core/database.py`
  - 第 88 行：参数化查询，使用运行时 user_agent_name

- **文件**: `src/agentmatrix/core/post_office.py`
  - 第 235 行：使用 `get_user_agent_name()` 进行比较

**更改**: 4 个文件，约 15 处替换

---

### 第四阶段：前端动态名称处理

#### 4.1 Web 应用更新
- **文件**: `web/js/app.js`
  - 第 79 行：用动态名称替换 `'User'` 过滤器
  - 第 202 行：用动态检查替换 `if (name === 'User')`
  - 添加 `/api/config` GET 端点调用，获取 user_agent_name

**代码变更**:
```javascript
// 从 API 获取 user agent 名称
let USER_AGENT_NAME = "User"; // 默认值
fetch('/api/config')
    .then(r => r.json())
    .then(config => { USER_AGENT_NAME = config.user_agent_name; });

// 使用动态名称
const filtered = rawAgents.filter(a => a !== USER_AGENT_NAME);
```

#### 4.2 客户端 HTML 更新
- **文件**: `client.html`
  - 第 161 行：使用动态名称记录日志

#### 4.3 添加配置 API 端点
- **文件**: `server.py`
  - 添加 `GET /api/config` 端点，返回 `user_agent_name`

**更改**: 3 个文件，约 20 行代码

---

### 第五阶段：CLI 支持和验证

#### 5.1 添加 CLI 交互
- **文件**: `cli_runner.py` 或创建新的 `cli_setup.py`
  - 添加 `--user-name` 命令行参数
  - 如果未提供，进入交互式输入模式
  - 检测冷启动并调用创建流程

**代码变更**:
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--user-name', type=str, help='User agent name')
args = parser.parse_args()

if is_cold_start:
    if not args.user_name:
        args.user_name = input("请输入 User Agent 名称: ")
    create_directory_structure(..., user_name=args.user_name)
```

#### 5.2 添加验证逻辑

这个不作为agentmatrix库的功能，这应该是应用功能。所以在server.py里，启动runtime后可以有一个检查步骤，
是否有user agent，是不是正确的类，有问题就启动server失败。


---

### 第六阶段：测试和文档

#### 6.1 测试计划
- **单元测试**:
  - 配置文件创建和读取
  - 模板变量替换
  - user agent 验证逻辑

- **集成测试**:
  - Web wizard 冷启动流程
  - CLI 冷启动流程
  - Runtime 初始化和 agent 加载

- **端到端测试**:
  - 创建新 world → 发送消息 → 验证名称正确
  - 多个不同名字的 world

#### 6.2 文档更新
- **更新 README.md**:
  - 说明冷启动时需要配置 User agent 名称
  - 提供示例截图

- **更新 API 文档**:
  - 新增 `/api/config` 端点文档
  - 更新冷启动流程说明



**更改**: 多个文档文件

---

## 🔄 配置流程（替代迁移策略）

### 新建 Matrix World 流程

**方式一：通过 Web Wizard**

```bash
# 1. 启动服务器（冷启动）
python server.py --matrix-world ./MyNewWorld

如果是冷启动，复制matrix_template的内容，获得基础的目录结构和一些默认的文件

# 2. 浏览器自动打开 wizard.html

# 3. Step 1/3: 输入 User Agent 名称
# 👤 请输入您的 User Agent 的名称: Alice
# ✅ 点击"下一步"

# 4. Step 2/3: 配置 LLM
# 输入 API URL、Key、Model
# ✅ 点击"下一步"

# 5. Step 3/3: 确认并创建
# ✅ 点击"创建 Matrix World"

# 6. 创建或者修改文件：
#    - MyNewWorld/matrix_world.yml (user_agent_name: "Alice")，这个创建
#    - MyNewWorld/agents/User.yml (name: Alice)，这个是复制来的，要修改
#    - MyNewWorld/agents/llm_config.json，这个创建


# 7. 自动初始化 Runtime 并进入主界面
```

**方式二：通过 CLI**

```bash
# 方式 A: 命令行参数
python cli_runner.py \
    --matrix-world ./MyNewWorld \
    --user-name Alice \
    --llm-api-url "https://api.deepseek.com" \
    --llm-api-key "sk-xxx" \
    --llm-model "deepseek-chat"

# 方式 B: 交互式输入
python cli_runner.py --matrix-world ./MyNewWorld

# 🔷 冷启动: 创建新的 Matrix World
# 请输入 User Agent 的名称: Alice
# 请输入 LLM API URL: https://api.deepseek.com
# 请输入 LLM API Key: sk-xxx
# 请输入 LLM Model: deepseek-chat

# ✅ 创建并启动...
```

### 配置文件验证

系统启动时自动验证：

```python
# 启动时检查
✅ 读取 matrix_world.yml
✅ 验证 user_agent_name: "Alice"
✅ 验证 User.yml 中的 name: "Alice" (匹配)
✅ 验证 UserProxyAgent 类正确
✅ 初始化 Runtime
```

如果验证失败：

```python
❌ 错误: 未找到名为 'Alice' 的 User agent
请检查 matrix_world.yml 中的配置是否正确
```



### 测试策略

测试都在 test 目录下进行

1. **冷启动流程测试**:
   - Web wizard 完整流程（各种输入组合）
   - CLI 交互式输入
   - CLI 参数化输入

2. **边界情况测试**:
   - 特殊字符用户名（中文、emoji、空格）
   - 极长名称
   - 保留字名称（如 "System"）

3. **错误恢复测试**:
   - 配置文件损坏
   - 模板文件缺失
   - API 失败
   - 网络中断

4. **集成测试**:
   - 端到端创建新 world
   - 发送消息验证名称正确
   - 数据库查询验证

---

## 📊 影响总结（更新版）

| 组件 | 需更改的文件 | 更改的行数 | 风险等级 | 备注 |
|------|-------------|-----------|---------|------|
| **冷启动基础设施** | 2 | ~60 | 中等 | 模板 + server.py |
| **Web Wizard** | 3 | ~100 | 中等 | HTML + JS + API |
| **Runtime 核心** | 5 | ~80 | 低 | runtime.py + 硬编码替换 |
| **前端动态处理** | 3 | ~20 | 低 | app.js + API |
| **CLI 支持** | 2 | ~40 | 低 | cli_runner.py + 验证 |
| **测试和文档** | 多个 | N/A | 无 | 测试用例 + 文档 |
| **总计** | **15+** | **~300+** | **中等** | 简化的实施路径 |



---

## ✅ 结论

**可行性**: ✅ **高度可行**

**推荐方案**: 冷启动时交互式配置 + 模板变量替换

**关键优势**:
1. ✅ **简洁清晰** - 无迁移复杂性
2. ✅ **一次性配置** - 只在冷启动时配置
3. ✅ **强制验证** - 确保配置正确
4. ✅ **易于维护** - 配置集中管理
5. ✅ **用户友好** - Web wizard 引导式配置

**实施建议**:
1. **优先实施 Web Wizard** - 这是主要入口点
2. **CLI 支持可以后续迭代** - 先保证 Web 流程完美
3. **充分的测试** - 聚焦冷启动流程的可靠性
4. **清晰的文档** - 帮助用户理解配置流程

**预期收益**:
- 用户可以自定义 User agent 名字
- 更好的国际化支持
- 更清晰的架构（无向后兼容包袱）
- 为未来功能扩展铺路（多用户支持等）

---

## 📚 相关文件清单（更新版）

### 需要修改的核心文件

#### 后端核心 (Python)
1. `server.py` - 冷启动流程、配置创建、API 端点
2. `src/agentmatrix/core/runtime.py` - 添加 user_agent_name 属性和 getter
3. `src/agentmatrix/core/loader.py` - 添加验证逻辑
4. `src/agentmatrix/core/database.py` - 参数化查询
5. `src/agentmatrix/core/post_office.py` - 动态名称比较
6. `cli_runner.py` - CLI 交互支持、参数解析（优先级最低）

#### 前端 (Web)
7. `web/wizard.html` - 添加 User 名称输入步骤
8. `web/js/app.js` 或 `web/js/wizard.js` - Wizard 逻辑、API 调用


#### 模板
10. `web/matrix_template/agents/User.yml` - 使用 `{{USER_NAME}}` 占位符
11. `web/matrix_template/agents/prompts/base.txt` - 使用 `{{USER_NAME}}` 占位符

### 需要新建的文件

1. **配置文件**（运行时创建）:
   - `<matrix_world>/matrix_world.yml` - World 级别配置

2. **测试文件**:
   - `test/test_cold_start.py` - 冷启动流程测试
   - `test/test_config.py` - 配置加载和验证测试
   - `test/test_template_replacement.py` - 模板替换测试

3. **文档**:
   - `docs/ColdStartGuide.md` - 冷启动配置指南（用户文档）
   - `docs/Architecture/UserAgentConfiguration.md` - 架构文档

### 不再需要的文件（简化）

- ❌ 移除迁移脚本（不需要向后兼容）
- ❌ 移除兼容性层代码
- ❌ 移除默认值逻辑

### 配置文件示例

**新建 World 后的文件结构**:

```
MyNewWorld/
├── matrix_world.yml          ← 新增：World 配置
│   └── user_agent_name: "Alice"
├── agents/
│   ├── User.yml              ← 动态生成：name: Alice
│   ├── llm_config.json       ← 现有：LLM 配置
│   └── prompts/
│       └── base.txt          ← 动态替换：User变成 Alice
└── workspace/
    └── .matrix/
        ├── user_sessions.json
        └── matrix_snapshot.json
```

---

**文档版本**: 2.0
**创建日期**: 2025-01-05
**最后更新**: 2025-01-06
**变更历史**:
- v2.0: 基于冷启动交互式配置重新设计，移除向后兼容和迁移相关内容
- v1.0: 初始版本（包含向后兼容方案）
