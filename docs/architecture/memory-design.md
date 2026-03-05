这是基于我们所有深入讨论（包括实体消歧、白板机制、后台异步流、自然语言主键等）重新梳理的最终版设计文档。

这份文档不仅是架构图，更是**开发指南**，直接指导工程落地。

---

# 交互式自然语言永久记忆系统设计文档 (v3.1 - 两层实体记忆架构版)

## 0. AgentMatrix 架构背景

在 AgentMatrix 中，Agent 的执行采用**嵌套 MicroAgent 架构**：

```
BaseAgent (管理会话)
  └─ 第一层 MicroAgent (有 whiteboard，可持久化)
      ├─ 第二层 MicroAgent (无 whiteboard，仅压缩)
      │   └─ 第三层 MicroAgent (无 whiteboard，仅压缩)
      └─ 第二层 MicroAgent (无 whiteboard，仅压缩)
```

**关键特点**：
- **BaseAgent**：管理 session、inbox、post_office 等全局组件
- **MicroAgent**：执行具体任务，每一层有独立的 messages context
- **父-子关系**：外层 MicroAgent 等待内层完成，内层返回结果
- **判断 Top-Level**：`isinstance(microagent.parent, BaseAgent)`

---

## 1. 核心设计哲学 (Core Philosophy)

本系统旨在构建一个**类人（Human-like）**的记忆机制，而非传统的 CRUD 数据库。

1.  **自然语言原生 (Natural Language Native)**：放弃传统的数据库外键 (`entity_id`)，以**自然实体名 (`Canonical Name`)** 作为显式连接键。实体间的关系由 LLM 阅读长文本档案自然理解。

2.  **交互式消歧 (Interactive Disambiguation)**：承认算法的不完美。当检索结果模糊或存在逻辑冲突时，**把判断权交给 LLM，通过向用户提问来解决**，而非后台盲目合并。

3.  **快慢双轨制 (Fast & Slow Memory)**：
    *   **前台 (Fast)**：通过"白板 (Whiteboard)"维护当前对话状态，保证短期记忆的连贯性。
    *   **后台 (Slow)**：异步进行"判官"式的实体匹配与档案重写，实现长期记忆的沉淀。

4.  **无模式档案 (Schema-less Profile)**：实体的核心数据是**纯文本**，允许记录任何非结构化的状态、偏好和历史。

5.  **层级记忆 (Hierarchical Memory)**：
    *   **Top-Level MicroAgent**：负责长期记忆的提交（写入 timeline + whiteboard.md）
    *   **内层 MicroAgent**：仅负责 context 压缩（避免 token 溢出）

6.  **两层实体记忆 (Two-Tier Entity Memory)**：
    *   **Session 实体记忆**：记录临时性、会话特定的信息（如"这次讨论中预算被拒绝了"）
    *   **全局实体记忆**：记录长期有价值的信息（如"张三是财务总监，风格保守"）
    *   **不去重原则**：允许信息重复，LLM 负责综合理解

---

## 2. 数据存储架构 (Storage Layer)

### 2.1 目录结构设计

基于 AgentMatrix 现有的 `.matrix` 目录结构，Memory 数据存储如下：

```
{workspace_root}/.matrix/
  {agent_name}/                       # Agent 级别（每个 Agent 独立）
    memory/
      global_memory.db                # ← 跨 session 实体库（Agent 的全局记忆）

    {user_session_id}/                # User 级别（每个用户独立）
      session_memory.db                # ← Session 实体 + 时间线（2 张表）
      whiteboard.md                    # ← Whiteboard 快照（Markdown 格式）
```

**设计说明**：
- ✅ `global_memory.db`：Agent 级别，跨 session 共享（Tom 的全局记忆，不是所有 Agent 共享）
  - 包含 1 张表：`Entity_Profiles`（全局实体档案）
- ✅ `session_memory.db`：User 级别，一个 user_session 对应一个文件
  - 包含 2 张表：
    - `Entity_Profiles`（Session 实体档案，临时信息）
    - `Timeline_Log`（时间线日志，原始事件）
- ✅ `whiteboard.md`：User 级别，与 `session_memory.db` 同目录

**简化优势**：
- ✅ 路径更短（从 6 层减少到 3 层）
- ✅ 逻辑清晰：一个 user_session 对应两个文件（session_memory.db + whiteboard.md）
- ✅ 易于管理：同一 user_session 的数据集中在一起

### 2.2 实体档案表 (`Entity_Profiles`)

**存储位置**：
- **全局**：`global_memory.db`
- **Session**：`session_memory.db`

**表结构**（两个数据库完全相同）：

*   **`uid` (String, PK)**: **隐形主键**（如 `u_a1b2`）。*注意：此 ID 仅用于底层 CRUD 和区分同名实体，对 LLM 的思考过程透明（LLM 只看名字）。*
*   **`canonical_name` (String)**: 标准自然名（允许重复！如库里可以有两个"张三"）。
*   **`aliases` (JSON List)**: 别名列表（如 `["张经理", "老张"]`）。
*   **`summary` (String)**: 一句话特征摘要（用于快速消歧，如"A项目后端开发"）。
*   **`profile_text` (Text)**: **核心字段**。纯自然语言的完整档案。

### 2.3 时间线日志表 (`Timeline_Log`)

存储在 `session_memory.db` 中：

*   **`log_id` (String, PK)**: 日志 ID。
*   **`timestamp` (DateTime)**: 事件发生时间。
*   **`content` (Text)**: **自包含**的事件描述（不含代词，实体名完整）。
*   **`processed` (Boolean)**: 是否已被后台合并，默认为 `False`。

### 2.4 并发控制与 WAL 模式

**并发场景分析**：

本系统存在**读写并发**的场景：
- **前台 LLM（读）**：Recall 操作查询 `session_memory.db` 和 `global_memory.db`
- **后台 Workers（写）**：Session Worker 写 `session_memory.db`，Global Worker 写 `global_memory.db`
- **前台 LLM（写）**：`update_memory` 写 `session_memory.db`

**冲突问题**：
- SQLite 默认的 **rollback journal** 模式：写操作会阻塞所有读操作
- 如果后台正在写，前台 Recall 会被阻塞 → **用户体验差**
- 如果前台正在读，后台写会被阻塞 → **Worker 性能差**

**解决方案：WAL 模式** ✅

**WAL (Write-Ahead Logging)** 模式的优势：
- ✅ **读写并发**：Writer 不会阻塞 Reader，Reader 也不会阻塞 Writer
- ✅ **更好的性能**：多个 Reader 可以并发读，一个 Writer 可以同时写
- ✅ **崩溃恢复**：更可靠的崩溃恢复机制

**配置要求**：
```python
# 所有数据库连接必须开启 WAL 模式
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA synchronous=NORMAL;")  # 平衡性能和安全
conn.execute("PRAGMA cache_size=-64000;")   # 64MB 缓存
```

**注意事项**：
- ⚠️ **额外文件**：WAL 模式会产生 `*.db-wal` 和 `*.db-shm` 文件
- ⚠️ **Checkpoint**：SQLite 自动管理 WAL 文件大小（默认 1000 页时 checkpoint）

---

## 3. 关键机制 I：前台交互循环 (The Foreground Loop)

此环节负责处理用户对话、短期记忆维护以及实体的"回忆与确认"。

### 3.1 动态上下文结构 (Context Structure)

LLM 的 System Prompt 包含两个区域：
1.  **Static Instructions**: 身份设定、Tool 使用规则。
2.  **The Whiteboard (动态白板)**: 当前对话的**状态快照 (Snapshot)**。
    *   *示例 Markdown*：
        ```markdown
        # 当前对话状态

        ## 主题
        用户正在讨论 Alpha 项目预算

        ## 涉及实体
        - 财务总监张三（新入职）

        ## 已确认决策
        - 预算从 50w 增加到 60w
        ```

### 3.2 Whiteboard 生命周期

```python
# Top-Level MicroAgent 初始化时加载
if isinstance(self.parent, BaseAgent):
    self.whiteboard = await self._load_whiteboard()  # 从 whiteboard.md 读取
    if not self.whiteboard:
        self.whiteboard = "# 对话开始"  # 初始状态

# 内层 MicroAgent 没有 whiteboard
# （因为 context 窄，仅看到子任务指令）
```

### 3.3 主动回忆机制 (Active Recall)

当 LLM 遇到上下文中未定义的实体和事实时，调用 `recall` 工具。

*   **输入**:
    *   `question` (必须): 要回忆什么（如"张三的职位是什么"）
    *   `entity_name` (必须): 应该隶属于哪个实体（如"张三"）
    *   `hint` (可选): 辅助线索（如"财务总监"）

*   **查询顺序**（🆕 删除 whiteboard 查询）:
    1.  **Session 实体记忆**（当前对话的临时信息）
    2.  **全局实体记忆**（跨 session 长期信息）

    > **注意**：Whiteboard 始终在 messages 中，LLM 每次都能看到，因此 recall 不需要专门查询 whiteboard。

*   **LLM 组织回答**:
    *   使用**小模型** (`cerebellum`) 来组织回答
    *   输入："问题" + "session_profiles" + "global_profiles"
    *   输出：综合两份档案的完整答案，或"没有找到相关信息"

*   **返回给 LLM 的信息**:
    对问题的答案（综合 session 和全局信息），或者说没找到回忆

---

## 4. 关键机制 II：记忆提交 (The Commit)

当对话告一段落、或完成重要信息澄清时，LLM **必须**调用 `update_memory` 工具。

### Tool 定义: `update_memory`

*   **调用方式**: `update_memory(focus_hint="...")`（可选参数）
*   **`focus_hint` (可选)**:
    *   **作用**: 指导 LLM 在生成 whiteboard 时**重点关注什么**。
    *   **用途**: 让总结更聚焦，突出特定方面。
    *   **示例**:
        *   `focus_hint="重点关注财务相关决策"` → whiteboard 会突出财务预算、审批流程
        *   `focus_hint="突出实体关系变化"` → whiteboard 会强调张三从"新同事"变为"财务总监"
        *   `focus_hint="记录当前待解决问题"` → whiteboard 会列出未解决的疑问

*   **Fork 机制**: 系统会获取当前 `self.messages`（完整会话历史），并启动两个独立的 LLM 调用：
    *   **LLM 实例 A**: 分析会话历史 → 生成 `new_whiteboard`（当前状态快照，**使用 focus_hint**）
    *   **LLM 实例 B**: 分析会话历史 → 生成 `memory_events`（关键事件增量，**不使用 focus_hint**）

*   **`new_whiteboard` (自动生成)**:
    *   **作用**: 更新 System Prompt，服务于下一轮对话。
    *   **内容**: 当前状态的**总结**（Snapshot）。丢弃过时的细节。
    *   **格式**: Markdown（如 `# 当前对话状态\n## 主题\n## 涉及实体\n## 已确认决策`）
    *   **🆕 受 `focus_hint` 影响**: 如果提供 focus_hint，总结会更聚焦

*   **`memory_events` (自动生成)**:
    *   **作用**: 发送给后台，用于永久记忆。
    *   **内容**: 自上次 Commit 以来发生的**关键事件增量**。
    *   **约束**: **严禁使用代词**（他/她/它），必须还原为实体全名。
    *   *示例*: `["用户确认将 Alpha 项目预算增加至 50 万", "财务总监张三拒绝了报销申请"]`

**优点**：
- ✅ **简化 LLM 负担**：不需要手动构造参数，调用 `update_memory()` 即可
- ✅ **自动提取**：从会话历史自动提取信息，不会遗漏
- ✅ **并行执行**：两个 LLM 调用并行，性能更好
- ✅ **一致性**：whiteboard 和 memory_events 都基于同一份会话历史，不会矛盾
- ✅ **灵活聚焦**：通过 `focus_hint` 引导 LLM 总结重点，让 whiteboard 更有针对性

### 行为分化（关键！）

`update_memory` 在不同层级的 MicroAgent 中有不同的行为：

| 操作 | Top-Level MicroAgent | 内层 MicroAgent |
|------|---------------------|----------------|
| **Whiteboard** | ✅ 更新内存 `self.whiteboard`<br>✅ 持久化到 `whiteboard.md` | ✅ 更新内存 `self.whiteboard`<br>❌ 不持久化 |
| **Timeline** | ✅ 写入 `session_memory.db` | ❌ 不写入 |
| **Workers** | ✅ 触发后台 workers | ❌ 不触发 |
| **Context 压缩** | ✅ 压缩 messages，继续循环 | ✅ 压缩 messages，继续循环 |

**判断 Top-Level**：
```python
is_top_level = isinstance(self.parent, BaseAgent)
```

### execute 循环改造

```python
class MicroAgent:
    async def execute(self, task_instruction, parent=None):
        # 初始化 whiteboard（仅 top-level）
        if isinstance(parent, BaseAgent):
            self.whiteboard = await self._load_whiteboard()

        while True:
            # 1. Think (LLM 决策下一步)
            action, args = await self._think()

            # 2. 检查是否需要退出
            if action in ["all_finished"]:
                break

            # 3. 执行 action
            result = await self._execute_action(action, args)

            # 4. 🆕 特殊处理 update_memory（可选 focus_hint，自动提取）
            if action == "update_memory":
                # 获取 focus_hint（可选参数）
                focus_hint = args.get("focus_hint", "")

                # 自动从会话历史提取信息（fork 机制）
                new_whiteboard, memory_events = await self._extract_from_history(focus_hint)

                # Top-Level: 额外持久化
                if isinstance(self.parent, BaseAgent):
                    await self._save_whiteboard(new_whiteboard)
                    await self._append_timeline(memory_events)
                    await self._trigger_workers()

                # 压缩 messages，继续下一轮循环
                await self._compress_messages(new_whiteboard)

                continue  # 不 append result，直接下一轮

            # 5. 正常流程：append result 到 messages
            self.messages.append({"role": "assistant", "content": result})

    async def _extract_from_history(self, focus_hint: str = ""):
        """🆕 Fork 机制：从会话历史自动提取信息"""
        # 1. 获取当前会话历史
        messages = self.messages

        # 2. 并发调用两个 LLM 总结
        whiteboard_task = self._generate_whiteboard_summary(messages, focus_hint)
        events_task = self._generate_memory_events(messages)

        # 3. 并行执行，等待结果
        new_whiteboard, memory_events = await asyncio.gather(
            whiteboard_task,
            events_task
        )

        return new_whiteboard, memory_events

    async def _generate_whiteboard_summary(self, messages, focus_hint: str = ""):
        """LLM 总结：生成 whiteboard（当前状态快照）"""
        prompt = f"""
分析以下对话历史，生成当前对话状态的总结。

要求：
1. Markdown 格式
2. 包含：当前主题、涉及实体、已确认决策
3. 简洁明了，丢弃过时细节
"""

        # 🆕 添加 focus_hint
        if focus_hint:
            prompt += f"""
**重点关注**：{focus_hint}

请在总结中特别突出这方面的信息。
"""

        prompt += f"""
对话历史：
{format_messages(messages)}

输出 whiteboard 内容：
"""
        llm = self.root_agent.cerebellum
        return await llm.generate(prompt)

    async def _generate_memory_events(self, messages):
        """LLM 总结：生成 memory_events（关键事件增量）"""
        prompt = f"""
分析以下对话历史，提取关键事件（用于长期记忆）。

要求：
1. 自包含的完整事件（不含代词）
2. 实体名必须完整
3. 仅包含有长期价值的信息

对话历史：
{format_messages(messages)}

输出 JSON 列表：
["事件1", "事件2", ...]
"""
        llm = self.root_agent.cerebellum
        return await llm.generate(prompt)

    async def _compress_messages(self, new_whiteboard: str):
        """压缩 messages，保留 system_prompt，添加总结"""
        # 保留 system_prompt
        system_msg = self.messages[0]

        # 压缩历史
        self.messages = [
            system_msg,
            {"role": "user", "content": f"[上下文总结]\n{new_whiteboard}\n\n请继续执行下一步。"}
        ]
```

---

## 5. 关键机制 III：后台异步固化 (Background Consolidation)

后台采用**两层架构**，分别处理 Session 级别和全局级别的实体记忆。

### 5.1 Session Entity Worker

**职责**：整理 `timeline` → `session_entities`（闲时执行）

```python
class SessionEntityWorker:
    """闲时整理 timeline → session_entities"""

    def __init__(self, agent: BaseAgent):
        self.agent = agent
        self.timeline_db = ...  # SQLite connection
        self.session_db = ...   # SQLite connection (session_entities)
        self.global_db = ...    # SQLite connection (global_entities，只读查询)
        self.paused = False

    async def start(self):
        """启动后台处理循环"""
        while True:
            # ⏸️ 检查是否应该暂停（Agent 在处理邮件）
            if self.agent.is_busy:
                await asyncio.sleep(1)
                continue

            # 查找未处理的 timeline events
            events = await self._fetch_unprocessed_events()

            for event in events:
                await self._process_event(event)

            await asyncio.sleep(5)

    async def _process_event(self, event):
        """处理单条事件：Extract -> Judge (全局+session) -> Historian"""
        # 1. Extract: 提取实体名
        entities = await self._extract_entities(event["content"])

        for entity_name in entities:
            # 2. 🔍 先查全局记忆（关键！）
            global_matches = await self._search_global_entities(entity_name)

            # 3. 查 session 实体记忆
            session_matches = await self._search_session_entities(entity_name)

            # 4. Judge: 判断 MATCH 全局 / MATCH session / NEW
            decision = await self._judge(
                entity_name, event,
                global_matches, session_matches
            )

            # 5. Historian: 更新或创建 session 实体档案
            if decision == "MATCH_SESSION":
                await self._update_session_entity(...)
            elif decision == "MATCH_GLOBAL":
                # 在 session 记录中注明"引用全局"
                await self._create_session_entity_ref_global(...)
            else:  # NEW
                await self._create_session_entity(...)
```

**关键逻辑**：
- ✅ 遇到新实体时，先查全局记忆
- ✅ 记录 session specific 的增量信息
- ✅ 允许与全局记忆重复

### 5.2 Global Entity Worker

**职责**：分析 `session_entities` → `global_entities`（闲时执行）

```python
class GlobalEntityWorker:
    """闲时分析 session_entities → global_entities"""

    def __init__(self, agent: BaseAgent):
        self.agent = agent
        self.session_db = ...   # SQLite connection (session_entities，只读查询)
        self.global_db = ...    # SQLite connection (global_entities)
        self.paused = False

    async def start(self):
        """启动后台处理循环"""
        while True:
            # ⏸️ 检查是否应该暂停（Agent 在处理邮件）
            if self.agent.is_busy:
                await asyncio.sleep(1)
                continue

            # 查找有更新的 session 实体
            updated_entities = await self._fetch_updated_session_entities()

            for session_entity in updated_entities:
                await self._process_entity(session_entity)

            await asyncio.sleep(10)  # 间隔更长

    async def _process_entity(self, session_entity):
        """处理单个 session 实体：分析价值 -> 决定是否迁移"""
        # 1. 分析：是否有"长期价值"？
        should_migrate = await self._analyze_long_term_value(session_entity)

        if should_migrate:
            # 2. 查找全局对应实体
            global_matches = await self._search_global_entities(session_entity["name"])

            # 3. 判断：是否需要合并/创建
            if global_matches:
                # 合并到全局实体档案
                await self._merge_to_global(session_entity, global_matches[0])
            else:
                # 创建新的全局实体档案
                await self._create_global_entity(session_entity)
```

**关键逻辑**：
- ✅ 分析是否有"长期价值"
- ✅ 决定是否合并到全局
- ✅ 不需要严格去重，允许重复

### 5.3 暂停/恢复机制

```python
class BaseAgent:
    async def process_email(self, email):
        # ⏸️ 暂停所有 Workers
        self.is_busy = True
        if self.session_worker:
            self.session_worker.paused = True
        if self.global_worker:
            self.global_worker.paused = True

        try:
            # 处理邮件...
            pass
        finally:
            # ▶️ 邮件处理完毕，恢复 Workers
            self.is_busy = False
            if self.session_worker:
                self.session_worker.paused = False
            if self.global_worker:
                self.global_worker.paused = False

    async def _start_workers(self):
        """启动闲时 Workers"""
        from ..skills.memory.session_worker import SessionEntityWorker
        from ..skills.memory.global_worker import GlobalEntityWorker

        self.session_worker = SessionEntityWorker(self)
        self.global_worker = GlobalEntityWorker(self)

        asyncio.create_task(self.session_worker.start())
        asyncio.create_task(self.global_worker.start())
```

### 5.4 LLM 使用策略

| 操作 | Worker | 使用的模型 | 说明 |
|------|--------|-----------|------|
| **session_worker.extract** | Session | `cerebellum` | 提取实体名 |
| **session_worker.judge** | Session | `cerebellum` | 判断 MATCH 全局/session/NEW |
| **session_worker.historian** | Session | `cerebellum` | 创建/更新 session 实体档案 |
| **global_worker.analyze** | Global | `cerebellum` | 分析是否有长期价值 |
| **global_worker.merge** | Global | `cerebellum` | 合并到全局实体档案 |
| **recall (组织回答)** | 前台 | `cerebellum` | 合并 session + 全局档案 |

---

## 6. 端到端工作流示例 (E2E Walkthrough)

### 场景 1：同名冲突与新实体创建（两层记忆）

1.  **用户**: "今天新来的那个**财务张三**，把我的报销单退回了。"
2.  **前台 Top-Level LLM**:
    *   调用 `recall("财务张三")`。
    *   **查 session**：没有记录。
    *   **查全局**：返回 `[{"uid":"u_1", "name":"张三", "summary":"A项目开发"}]`。
    *   **思考**: 名字匹配，但用户说是"新来的财务"，跟"开发"冲突。
    *   **回复用户**: "你提到的这个财务张三，和咱们之前聊的那个做开发的张三是两个人对吧？"
3.  **用户**: "对，是两个人。"
4.  **前台 Top-Level LLM**:
    *   调用 `update_memory(focus_hint="突出新实体识别和财务相关决策")`（🆕 使用 focus_hint）。
    *   **系统自动执行（Fork 机制）**：
        *   **LLM A** 生成 `new_whiteboard`:
            ```markdown
            # 当前对话状态

            ## 主题
            识别新同事：财务总监张三（与开发张三不同）

            ## 涉及实体
            - 财务总监张三（新入职，退回报销单）

            ## 已确认决策
            - 报销单被退回（待重新提交）
            ```
        *   **LLM B** 生成 `memory_events`: `["用户确认存在一个新实体：财务总监张三", "财务总监张三退回了用户的报销单"]`
    *   **执行**:
        *   更新 whiteboard（内存 + whiteboard.md）
        *   写入 session_memory.db
        *   触发 workers
5.  **后台 Session Worker (异步，闲时执行)**:
    *   读取 `memory_events`。
    *   **Judge**：
        *   先查全局：有"张三 (A项目开发)"
        *   判断：是 NEW_ENTITY（与全局不同人）
    *   **Historian**: 创建 **session 实体档案**：
        ```json
        {
          "uid": "s_u_1",
          "name": "张三",
          "summary": "财务总监（新入职）",
          "profile_text": "财务总监张三，在这次对话中退回了用户的报销单。与开发张三是不同人。"
        }
        ```
6.  **后台 Global Worker (异步，闲时执行)**:
    *   分析 session 实体档案。
    *   **判断**: 有长期价值（新同事信息）。
    *   **创建全局实体档案**：
        ```json
        {
          "uid": "u_2",
          "name": "张三",
          "summary": "财务总监",
          "profile_text": "财务总监张三，新入职。风格保守，注重流程合规。"
        }
        ```

### 场景 2：跨 Session 的记忆积累

**Session 1（2月1日）**：
- 用户介绍"财务张三"，偏好保守决策
- Session Worker: 创建 session 实体档案
- Global Worker: 判断有长期价值，创建全局实体档案

**Session 2（2月15日）**：
- 用户提到"财务张三"拒绝了 Alpha 项目预算（60w）
- Session Worker: 更新 session 实体档案（记录拒绝事件）
- Global Worker: 可能合并（如果判断有价值）

**Session 3（今天）**：
- 用户问："张三之前对预算的态度是什么？"
- Recall:
  - 查 session: "张三拒绝了 Alpha 项目 60w 预算"
  - 查全局: "张三是财务总监，偏好保守决策"
  - LLM 合并: **"张三是财务总监，风格偏好保守决策。在 2月15日 的对话中，他拒绝了 Alpha 项目 60w 的预算申请。"**

### 场景 3：内层 MicroAgent 的 context 压缩

1.  **Top-Level LLM**: 委派任务给第二层 MicroAgent。
2.  **第二层 MicroAgent**:
    *   执行复杂的子任务（如浏览器搜索 + 分析）。
    *   Messages 过长（接近 token 限制）。
    *   LLM 决定调用 `update_memory()`（🆕 无参数）。
    *   **系统自动执行（Fork 机制）**：
        *   **LLM A** 生成 `new_whiteboard`: "已搜索 3 个网站，找到 Alpha 项目预算信息..."
        *   **LLM B** 生成 `memory_events`: []（空列表，因为是内层任务，不持久化）
    *   **执行**:
        *   压缩 messages（保留 system_prompt + 总结）
        *   继续下一轮循环
        *   ❌ 不写入 timeline（因为是内层）
3.  **第二层 MicroAgent**: 完成任务，返回结果给 Top-Level。
4.  **Top-Level LLM**: 根据返回结果，决定是否 `update_memory`（持久化）。

---

## 7. 技术实现要点

### 7.1 目录结构

```
src/agentmatrix/skills/memory/
  ├── __init__.py              # 导出 MemorySkillMixin
  ├── skill.py                 # 核心 Actions (recall, update_memory)
  ├── storage.py               # SQLite 数据库封装（含 WAL 配置）
  ├── session_worker.py        # 🆕 Session Entity Worker
  ├── global_worker.py         # 🆕 Global Entity Worker
  └── whiteboard.py            # Whiteboard 管理工具（可选）
```

### 7.2 SQLite WAL 模式配置

```python
import sqlite3
from pathlib import Path

class StorageManager:
    """SQLite 数据库管理器（支持 WAL 模式）"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """连接数据库并开启 WAL 模式"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)

        # ✅ 开启 WAL 模式（关键！）
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")  # 平衡性能和安全
        self.conn.execute("PRAGMA cache_size=-64000;")   # 64MB 缓存

        self.conn.row_factory = sqlite3.Row  # 返回字典格式

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

# 使用示例
async def get_global_db(workspace_root: str, agent_name: str) -> StorageManager:
    """获取全局记忆数据库连接"""
    db_path = os.path.join(
        workspace_root,
        ".matrix",
        agent_name,
        "memory",
        "global_memory.db"
    )
    # 示例：MyWorld/workspace/.matrix/Tom/memory/global_memory.db

    storage = StorageManager(db_path)
    await storage.connect()

    # 初始化表结构
    storage.conn.execute("""
        CREATE TABLE IF NOT EXISTS Entity_Profiles (
            uid TEXT PRIMARY KEY,
            canonical_name TEXT,
            aliases JSON,
            summary TEXT,
            profile_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    storage.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_name
        ON Entity_Profiles(canonical_name)
    """)

    return storage
```

**关键配置说明**：
- `PRAGMA journal_mode=WAL;`: 开启 WAL 模式（必须）
- `PRAGMA synchronous=NORMAL;`: 平衡性能和数据安全（默认 FULL 太慢）
- `PRAGMA cache_size=-64000;`: 增加缓存到 64MB（提升性能）

### 7.3 判断 Top-Level

```python
# 在 MemorySkillMixin 中
def _is_top_level(self):
    """判断是否是 top-level MicroAgent"""
    return isinstance(self.parent, BaseAgent)
```

### 7.4 Recall 实现（合并两份档案）

```python
async def recall(self, question: str, entity_name: str, hint: str = ""):
    """回忆实体或事实（从两个地方获取）"""

    # 1. Session 实体记忆（临时信息）
    session_profiles = await self._search_session_entities(entity_name, hint)

    # 2. 全局实体记忆（长期信息）
    global_profiles = await self._search_global_entities(entity_name, hint)

    # 3. 🆕 LLM 合并两份档案
    answer = await self._llm_merge_profiles(
        question=question,
        entity_name=entity_name,
        session_profiles=session_profiles,  # 临时信息
        global_profiles=global_profiles      # 长期信息
    )

    return answer

async def _llm_merge_profiles(self, question, entity_name, session_profiles, global_profiles):
    """调用 LLM 合并 session 和全局档案"""
    prompt = f"""
基于以下信息回答用户的问题：

问题：{question}
实体名：{entity_name}

=== 会话级实体档案（临时信息）===
{format_profiles(session_profiles)}

=== 全局实体档案（长期信息）===
{format_profiles(global_profiles)}

请综合两份档案，给出完整的答案。如果信息有重复，自然整合即可。如果没有找到相关信息，请说明"没有找到相关信息"。
"""

    llm = self.root_agent.cerebellum
    response = await llm.generate(prompt)
    return response
```

### 7.5 update_memory 实现（Fork 机制）

```python
@register_action(
    "更新记忆。当对话告一段落或完成重要信息澄清时调用此 action。",
    param_infos={
        "focus_hint": "可选。指导总结重点，如'重点关注财务决策'、'突出实体关系变化'等"
    }
)
async def update_memory(self, focus_hint: str = ""):
    """更新记忆（自动从会话历史提取）"""

    # 1. 获取当前会话历史
    messages = self.messages

    # 2. 并发调用两个 LLM 总结（并行执行）
    whiteboard_task = self._generate_whiteboard_summary(messages, focus_hint)
    events_task = self._generate_memory_events(messages)

    # 3. 并行执行，等待结果
    new_whiteboard, memory_events = await asyncio.gather(
        whiteboard_task,
        events_task
    )

    # 4. Top-Level: 持久化
    if isinstance(self.parent, BaseAgent):
        await self._save_whiteboard(new_whiteboard)
        await self._append_timeline(memory_events)
        await self._trigger_workers()

    # 5. 压缩 messages（所有层级）
    await self._compress_messages(new_whiteboard)

    return "记忆已更新"

async def _generate_whiteboard_summary(self, messages, focus_hint: str = ""):
    """LLM 总结：生成 whiteboard（当前状态快照）"""
    prompt = f"""
分析以下对话历史，生成当前对话状态的总结。

要求：
1. Markdown 格式（# 当前状态\n## 主题\n## 涉及实体\n## 已确认决策）
2. 简洁明了，丢弃过时细节
"""

    # 🆕 添加 focus_hint
    if focus_hint:
        prompt += f"""
**重点关注**：{focus_hint}

请在总结中特别突出这方面的信息。
"""

    prompt += f"""
对话历史：
{format_messages(messages)}

输出 whiteboard 内容：
"""
    llm = self.root_agent.cerebellum
    return await llm.generate(prompt)

async def _generate_memory_events(self, messages):
    """LLM 总结：生成 memory_events（关键事件增量）"""
    prompt = f"""
分析以下对话历史，提取关键事件（用于长期记忆）。

要求：
1. 自包含的完整事件（不含代词）
2. 实体名必须完整
3. 仅包含有长期价值的信息

对话历史：
{format_messages(messages)}

输出 JSON 列表：
["事件1", "事件2", ...]
"""
    llm = self.root_agent.cerebellum
    return await llm.generate(prompt)

async def _compress_messages(self, new_whiteboard: str):
    """压缩 messages，保留 system_prompt，添加总结"""
    system_msg = self.messages[0]
    self.messages = [
        system_msg,
        {"role": "user", "content": f"[上下文总结]\n{new_whiteboard}\n\n请继续执行下一步。"}
    ]
```

---

## 8. 开发路线图 (Implementation Roadmap)

### P0 - 基础设施
- [ ] 创建 `skills/memory/` 目录结构
- [ ] 实现 `storage.py`: SQLite 数据库封装（✅ 必须开启 WAL 模式）
    *   `StorageManager` 类：连接管理、表初始化
    *   **WAL 模式配置**：
        *   `PRAGMA journal_mode=WAL;`（必须）
        *   `PRAGMA synchronous=NORMAL;`
        *   `PRAGMA cache_size=-64000;`
    *   `global_memory.db` 表结构（1 张表：Entity_Profiles）
    *   `session_memory.db` 表结构（2 张表：Entity_Profiles + Timeline_Log）
    *   CRUD 操作封装
    *   **测试**：验证读写并发不会阻塞
- [ ] 实现 `whiteboard.py`: Whiteboard 加载/保存工具
    *   `load_whiteboard(agent_name, user_session_id)`
    *   `save_whiteboard(content, agent_name, user_session_id)`

### P1 - 前台 Loop
- [ ] 实现 `skill.py`: recall action
    *   查 session 实体记忆（临时信息）
    *   查全局实体记忆（长期信息）
    *   调用 cerebellum 合并两份档案
    *   🚫 删除 whiteboard 查询（始终在 messages 中）
- [ ] 实现 `skill.py`: update_memory action（🆕 Fork 机制 + focus_hint）
    *   **可选参数**：`focus_hint`（指导总结重点）
    *   **自动提取**：从 `self.messages` 提取信息
    *   **并行生成**：
        *   `_generate_whiteboard_summary(messages, focus_hint)`: 生成 whiteboard（受 focus_hint 影响）
        *   `_generate_memory_events(messages)`: 生成 memory_events（不受 focus_hint 影响）
    *   **行为分化**：
        *   Top-Level: 更新 whiteboard + 写 timeline + 触发 workers
        *   内层: 仅压缩 messages（不做持久化）
- [ ] 改造 `micro_agent.py`: execute 循环
    *   检测 `update_memory` action
    *   获取 `focus_hint` 参数（可选）
    *   调用 `_extract_from_history(focus_hint)`（fork 机制）
    *   调用 `_compress_messages()`
    *   `continue` 下一轮（不 append result）
    *   初始化 whiteboard（仅 top-level）

### P2 - 记忆提交
- [ ] 实现 `skill.py`: _append_timeline
    *   写入 session_memory.db
    *   标记 `processed=False`
- [ ] 实现 `skill.py`: _save_whiteboard
    *   写入 whiteboard.md（Markdown 格式）
- [ ] 实现 `skill.py`: _trigger_workers
    *   设置标志位或放入队列

### P3 - 后台 Workers
- [ ] 实现 `session_worker.py`: SessionEntityWorker 类
    *   `start()`: 后台循环（检查暂停）
    *   `_fetch_unprocessed_events()`
    *   `_process_event()`: Extract -> Judge (全局+session) -> Historian
    *   Extract: 提取实体名
    *   Judge: 先查全局，再查 session，判断 MATCH 全局/session/NEW
    *   Historian: 创建/更新 session 实体档案
- [ ] 实现 `global_worker.py`: GlobalEntityWorker 类
    *   `start()`: 后台循环（检查暂停，间隔更长）
    *   `_fetch_updated_session_entities()`
    *   `_process_entity()`: 分析价值 -> 决定是否迁移
    *   Analyze: 判断是否有长期价值
    *   Merge: 合并到全局实体档案
- [ ] 集成到 `base.py`:
    *   实现 `is_busy` 标志
    *   在 `process_email` 中暂停/恢复 workers
    *   启动两个后台 workers

---

这份文档现在可以直接发给开发人员进行代码实现了。它既保留了自然语言交互的灵活性，又在工程上解决了数据一致性和消歧的难题，同时完美适配 AgentMatrix 的嵌套 MicroAgent 架构和两层实体记忆设计。
