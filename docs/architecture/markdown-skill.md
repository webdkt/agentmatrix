这是一份基于我们深度讨论后，重新梳理的**《基于 AgentMatrix 的超大 Markdown 处理系统架构设计文档》**。

这套设计彻底摒弃了传统 RAG（向量数据库）和全局文件读取的弊端，采用**“双层代理架构 (Two-Tier Architecture) + AST 虚拟文件树 + 动态微智能体”**的模式，是处理超大结构化文本的终极解法。

---

# 超大 Markdown 处理系统架构设计文档

## 一、 系统整体架构 (Two-Tier Architecture)

为了保持 BaseAgent (主控 Agent) 的极致轻量和专注，我们将 Markdown 的处理能力拆分为**内外两层**。BaseAgent 只负责下达宏观意图，脏活累活全部在隔离的沙盒中闭环完成。

### 1. 外层代理代理：`MarkdownManagerSkill`
*   **挂载对象**：BaseAgent 或上层通用 MicroAgent。
*   **职责**：充当“项目经理”，隐藏所有底层 AST 与分块细节。
*   **对外暴露的唯一 Action**：
    ```python
    def process_markdown(file_path: str, intention: str) -> str:
        """
        处理或编辑指定的 Markdown 文件。
        :param file_path: 文件路径
        :param intention: 自然语言描述的具体意图（例："找出第二章关于AI的段落，将其扩写并增加2027年的预测数据"）
        :return: 任务执行结果报告（供 BaseAgent 阅读）
        """
    ```
*   **运行机制**：当被触发时，该接口会在内存中解析文件生成 AST 树，**动态孵化一个专属的 `MarkdownWorkerAgent`**，并将 AST 树和底层工具箱交给它执行闭环任务。任务完成后，销毁 WorkerAgent 并保存文件。

### 2. 内层工作引擎：`MarkdownWorkerAgent` (MicroAgent)
*   **生命周期**：被 `process_markdown` 临时唤醒，执行完 `intention` 即销毁。
*   **职责**：在沙盒中自主进行“思考-观察-行动 (ReAct)”，使用底层工具箱（Core Skill）完成具体的查找、阅读、修改闭环。

### 3. 底层工具箱：`MarkdownASTCoreSkill`
*   **挂载对象**：专属于 `MarkdownWorkerAgent`。
*   **职责**：直接操作内存中的 AST 树，提供导航、查询、读写的原子化 API。

---

## 二、 核心数据结构：虚拟语法树 (AST)

整个系统不直接操作字符串，而是将 Markdown 解析为带有丰满 Metadata 的树状结构。

```python
from typing import List, Optional, Dict
from pydantic import BaseModel

class MarkdownNode(BaseModel):
    # --- 1. 定位与层级 ---
    node_id: str                  # 绝对路径 ID (如: "root/h1_1/h2_2/p_3")
    node_type: str                # 节点类型 ("root", "h1", "h2", "paragraph", "code_block", "table")
    title: Optional[str] = None   # 可读标题 (如: "1.1 背景介绍")，加速大纲生成
    
    # --- 2. 节点内容 ---
    content: str                  # 节点自身的纯文本 (如果是 Heading，仅包含 "# 标题" 本身)
    children: List['MarkdownNode'] =[] # 子节点列表
    
    # --- 3. 元数据与状态 ---
    char_count: int = 0           # 字符数
    token_count: int = 0          # 估算 Token 数
    is_dirty: bool = False        # 脏标记 (被修改过为 True，用于触发局部渲染)
    
    # --- 4. 防御性切分 (Virtual Chunking) ---
    is_large_node: bool = False   # 是否超过安全 Token 阈值 (如 2000 tokens)
    virtual_chunks: Optional[List[Dict]] = None 
    # 记录超大节点的虚拟分块偏移量（相对当前 content 的位置，绝对安全）：
    #[
    #   {"chunk_id": "root/h1_1/code_1/chunk_01", "start_char": 0, "end_char": 1500},
    #   {"chunk_id": "root/h1_1/code_1/chunk_02", "start_char": 1500, "end_char": 3200}
    # ]
```

---

## 三、 底层工具箱动作设计 (`MarkdownASTCoreSkill` Schema)

供 `MarkdownWorkerAgent` 调用的函数接口。**核心原则：JSON 参数中坚决不传递大段 Markdown 文本！**

### 1. 导航与定位 (Navigation & Search)
*   **`get_toc(depth: int = 2)`**
    *   获取文档层级大纲及 `node_id`。
*   **`search_keywords(query: str, context_lines: int = 2)`**
    *   全文关键字/正则扫描，返回命中列表（包含 `node_id` 及前后两行上下文快照）。

### 2. 精准阅读 (Read)
*   **`read_node_content(node_id: str)`**
    *   拉取具体节点内容。如果遇到超大节点，系统自动拦截并提示：“该节点过大，请指定 chunk_01 ~ chunk_0N”。

### 3. 指令式编辑 (Instruction-based Edit)
*   **`exact_replace(node_id: str, old_str: str, new_str: str)`**
    *   用于极小范围的错别字/名词替换。
*   **`rewrite_node(node_id: str, edit_instruction: str)`**  **(核心！)**
    *   **机制**：WorkerAgent 仅输出修改指令（如 *"扩写，加入 2027 年数据"*）。底层 Python 拦截指令，拉取该节点原文，**并发孵化一个更底层的“打字员 MicroAgent”** 生成修改后的纯文本，然后安全更新 AST 树。
*   **`append_new_node(parent_id: str, instruction: str)`**
    *   在特定层级下新增由指令生成的内容节点。

### 4. 总结 (Map-Reduce Summarize)
*   **`summarize_node(node_id: str)`**
    *   针对特定章节孵化子 Agent 生成摘要。
*   **`summarize_document()`**
    *   针对超大文件，自动遍历 H1 节点并发生成分段摘要，最后合并为全局摘要。

---

## 四、 内层引擎：`MarkdownWorkerAgent` 的 Prompt 设计

这个 Agent 运行在一个封闭的 ReAct 循环中，必须通过严格的 System Prompt 约束其行为。

**System Prompt (示例):**
```text
你是一个专业的 Markdown 文档处理引擎。你当前被挂载了一个虚拟的 AST 文件树。
你的唯一任务是完成用户下达的 [Intention]。

【工作规范与步骤】
1. 你绝对不能凭空猜测文档内容。在修改任何东西前，必须先进行“调查”。
2. 调查第一步：调用 `get_toc()` 查看文档骨架，锁定疑似章节。
3. 调查第二步：如果大纲无法定位，调用 `search_keywords()` 获取上下文快照。
4. 调查第三步：找到目标 ID 后，调用 `read_node_content()` 获取原文。
5. 修改阶段：确定修改方案后，绝对不要自己输出大段 Markdown！你必须调用 `rewrite_node()` 或 `exact_replace()`，把修改意图作为指令传递给底层工具。

【ID 寻址规则】
- 所有节点都有唯一路径 ID (如 root/h1_2/p_3)。
- 如果遇到超大节点被切分，必须带上 chunk 后缀 (如 root/h1_2/code_1/chunk_02) 进行操作。

【终止条件】
当你认为 [Intention] 已经完美达成，或者你确认文档中不存在相关信息时，请结束任务，并向你的上级返回一份清晰的【执行日志摘要】（告知你修改了哪些节点，或什么也没做）。
```

---

## 五、 全链路执行流演练 (Workflow Walkthrough)

**场景：处理一份 10 万字的 `report.md`。**
**用户意图：“总结第三章的内容，并且如果里面提到了‘旧系统’，请改写为‘遗留系统’。”**

1. **宏观派发 (BaseAgent)**：
   * BaseAgent 决定调用外层能力：`call:process_markdown{file_path: "report.md", intention: "总结第三章，将其中的'旧系统'统一改写为'遗留系统'"}`。

2. **沙盒构建 (Manager Skill 拦截)**：
   * 框架在内存中解析 `report.md`，构建 AST 树。
   * 孵化出 `MarkdownWorkerAgent`。

3. **自主工作 (WorkerAgent ReAct Loop)**：
   * **Loop 1**: WorkerAgent 思考需要找“第三章”，调用 `call:get_toc{depth: 1}`。
   * **返回 1**: 收到大纲，发现第三章 ID 是 `root/h1_3`。
   * **Loop 2**: WorkerAgent 思考任务要求总结并替换，先调用 `call:summarize_node{node_id: "root/h1_3"}`。
   * **返回 2**: 收到第三章的摘要（底层由子 Agent 并发生成完毕）。
   * **Loop 3**: 针对“旧系统”替换任务，WorkerAgent 调用 `call:search_keywords{query: "旧系统"}`。
   * **返回 3**: 系统返回：命中 2 处，位于 `root/h1_3/p_5` 和 `root/h1_3/chunk_02`。
   * **Loop 4**: WorkerAgent 依次调用 `call:exact_replace{node_id: "root/h1_3/p_5", old_str: "旧系统", new_str: "遗留系统"}`，完成替换。
   * **完成**: WorkerAgent 结束循环，输出执行日志。

4. **落盘与汇报**：
   * Manager Skill 接收到日志，将内存中脏掉的 AST 树重新渲染并覆盖保存到 `report.md`。
   * 销毁 WorkerAgent。
   * 将执行日志和第三章摘要作为 String 返回给 BaseAgent。

5. **任务闭环**：
   * BaseAgent 拿到结果，以自然舒适的语气回复用户。

---

### 架构优势总结
1. **彻底解决大文本 Context 爆炸**：仅有被查询的叶子节点进入大模型上下文。
2. **根除 JSON 转义地狱**：复杂 Markdown 的生成全部由底层的纯文本 Prompt (子 MicroAgent) 承担，Schema 调度的都是简短字符串。
3. **极简的高层逻辑**：BaseAgent 甚至感觉不到这是一份 10 万字的文件，它只是在下发高级指令，系统的伸缩性和鲁棒性达到了极致。

---

## 六、 AST 解析器实现方案（已确定）

> 本章节记录了 AST 解析器的技术选型和实现细节，这些方案已经过讨论并确定。

### 1. 技术选型

**选择：`markdown-it-py`**

**理由**：
- ✅ 极度合规且快速：是最强 JS 解析器 markdown-it 的 Python 移植版，严格遵守 CommonMark
- ✅ 完美的 Token Stream 机制：生成扁平的 Token 列表（具有 heading_open, inline, heading_close 等成对状态）
- ✅ 行号映射（Source Map）：Token 自带原文本的起止行号（`token.map`），能无损切片原始文本
- ✅ 不会误判代码块内的 Markdown 语法（如 `#` 在代码块内不会被识别为标题）

**坚决不使用**：
- ❌ 原生 Python markdown 库：核心目标是转译 HTML，极难逆向还原出带有精确字符偏移量的原始 Markdown
- ❌ 正则表达式：Markdown 的嵌套规则极度复杂（如列表中嵌套代码块，代码块里有 #），正则会瞬间崩溃

---

### 2. 四阶段 Pipeline 架构

整个 AST 解析器被设计为一个流水线（Pipeline），包含四个阶段：

#### 阶段 1：词法扫描 (Lexer & Tokenization)

**输入**：原始的超大 String（或从文件分块读取）

**动作**：使用 markdown-it-py 将纯文本解析为扁平的 Token 流

**输出**：
```python
[
    Token(heading_open, level=1),
    Token(inline, content="一、起步"),
    Token(heading_close, level=1),
    Token(paragraph_open),
    Token(inline, content="这是第一段"),
    Token(paragraph_close),
    ...
]
```

#### 阶段 2：逻辑折叠与树构建 (Logical Tree Builder)

这是最关键的自定义逻辑！使用一个 **栈（Stack）状态机**，把扁平的 Token 流折叠成 MarkdownNode 树。

**核心算法（Stack-based Folding）**：
1. 维护一个栈，初始时推入 RootNode
2. 遍历 Token 流，根据原始行号切片获取该 Token 的原汁原味内容
3. 遇到非标题块（Paragraph, Code, Table）：直接作为当前栈顶节点的子节点
4. 遇到标题块（H1 ~ H6）：
   - 比较当前标题级别与栈顶节点的级别
   - 如果当前级别 > 栈顶级别：将当前标题作为栈顶的子节点，压入栈顶
   - 如果当前级别 == 栈顶级别：弹出栈顶，将当前标题作为新栈顶的子节点，压入栈顶
   - 如果当前级别 < 栈顶级别：一直弹栈，直到栈顶级别 > 当前级别，然后将当前标题作为栈顶的子节点，压入栈顶

**边界情况处理**：
- **标题跳跃（H1 → H3）**：直接入栈，不补虚拟节点（Markdown 本身就允许标题跳跃）
- **标题回退（H1 → H2 → H3 → H2）**：弹出 H3，将新 H2 作为 H1 的子节点
- **非标题块**：直接作为当前栈顶节点的子节点（如 Paragraph 位于两个 H2 之间，父节点是第一个 H2）

#### 阶段 3：元数据与防御性切分 (Enrichment & Chunking Engine)

树结构建好后，进行一次深度优先遍历（DFS）：

1. **计算 Token / 字符数**：统计每个节点的 `char_count` 和 `token_count`
2. **触发虚拟切分（Virtual Chunking）**：
   - **阈值**：8K tokens（已确定）
   - 如果某个叶子节点超过阈值，触发 ChunkingEngine

**切分策略（降级瀑布流）**：
1. 尝试按 `\n\n` 切（保证段落完整）
2. 若单段仍超标，按 `\n` 切（保证代码行/表格行完整）
3. 若仍超标（极端情况），按标点符号 `。`、`.` 切
4. 最后手段：按固定字符数强制切分

**虚拟分块数据结构**：
```python
class VirtualChunk:
    chunk_id: str  # "root/h1_1/code_1/chunk_01"
    start_char: int  # 相对 parent content 的起始位置
    end_char: int    # 相对 parent content 的结束位置

    @property
    def content(self) -> str:
        # 从 parent.content 切片
        return self.parent.content[self.start_char:self.end_char]
```

**修改逻辑**：
- 用户修改某个 chunk 的内容
- 更新 `parent.content` 中对应的片段
- 重新计算所有 chunk 的 `start_char` 和 `end_char`

#### 阶段 4：寻址与 ID 挂载 (Addressing & ID Generation)

再次遍历 AST，为每个节点生成类似 `root/h1_1/h2_2/p_3` 的绝对路径 ID：

- 同级节点通过计数器自增后缀（_1, _2）
- 这步必须放在最后，确保 ID 严格反映文档的物理先后顺序

---

### 3. MarkdownNode 数据结构（确定版）

```python
from typing import List, Optional, Dict
from pydantic import BaseModel

class MarkdownNode(BaseModel):
    # --- 1. 定位与层级 ---
    node_id: str                  # 绝对路径 ID (如: "root/h1_1/h2_2/p_3")
    node_type: str                # 节点类型 ("root", "h1", "h2", "paragraph", "code_block", "table")
    title: Optional[str] = None   # 可读标题 (如: "1.1 背景介绍")，加速大纲生成

    # --- 2. 节点内容 ---
    content: str                  # 节点自身的纯文本
                                  # 如果是 Heading，不包含 # 符号（如 "第一章" 而非 "# 第一章"）
    children: List['MarkdownNode'] = []  # 子节点列表

    # --- 3. 元数据与状态 ---
    char_count: int = 0           # 字符数
    token_count: int = 0          # 估算 Token 数
    is_dirty: bool = False        # 脏标记 (被修改过为 True，用于触发局部渲染)

    # --- 4. 防御性切分 (Virtual Chunking) ---
    is_large_node: bool = False   # 是否超过安全 Token 阈值（8K tokens）
    virtual_chunks: Optional[List[VirtualChunk]] = None
    # 记录超大节点的虚拟分块偏移量（相对当前 content 的位置）
```

**关键设计决策**：
- ✅ 标题节点的 `content` **不包含** `#` 符号（如 "第一章" 而非 "# 第一章"）
- ✅ 非标题块（Paragraph, Code）作为当前栈顶节点的子节点
- ✅ 虚拟分块的阈值设为 **8K tokens**

---

### 4. Token 内容提取方案

由于 `markdown-it-py` 的 `token.map` 只提供行号范围（`[start_line, end_line]`），需要自己实现 `ContentExtractor`：

```python
class TokenContentExtractor:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.lines = raw_text.split('\n')  # 保留所有行

    def extract_content(self, token: Token) -> str:
        if token.map is None:
            return ""

        start_line, end_line = token.map

        # 提取对应行（注意 line number 是从 0 开始的）
        lines = self.lines[start_line:end_line + 1]
        return '\n'.join(lines)
```

**使用方式**：
```python
extractor = TokenContentExtractor(raw_markdown_text)
for token in tokens:
    content = extractor.extract_content(token)
    # 使用 content 构建 MarkdownNode
```

---

### 5. 渲染器设计（逆向过程）

有了完美的解析器，渲染过程极其简单且无损：

**核心思想**：由于在 `MarkdownNode.content` 中保留了"原汁原味"的 Markdown 源码切片，只需对 AST 进行一次 DFS 遍历，拼接所有节点的内容。

**伪代码**：
```python
def render_tree(node: MarkdownNode) -> str:
    result = node.content

    for i, child in enumerate(node.children):
        # 根据节点类型决定换行符
        if node.node_type == "root":
            separator = ""
        elif node.node_type in ["h1", "h2", "h3"]:
            separator = "\n"
        elif node.node_type == "paragraph":
            separator = "\n\n"
        else:
            separator = "\n"

        result += separator + render_tree(child)

    return result
```

**优雅之处**：
- 无论经过多少次 MicroAgent 的局部修改，只要替换了对应节点的 `content`，重新跑一遍 `render_tree()`，就能完美输出拼装好的新 `.md` 文件
- 完全不用担心丢失原始文档中的自定义 HTML 标签或特殊缩进

---

### 6. 架构边界

```python
Parser: File → AST Tree
    ↓
ASTManager: CRUD + Chunking
    ↓
Renderer: AST Tree → File
    ↓
Agent Skill: 调用 ASTManager 的接口
```

**职责划分**：
- **Parser 类**：只负责 File → AST Tree
- **Renderer 类**：只负责 AST Tree → File
- **ASTManager 类**：封装对这棵树的 CRUD（增删改查）操作，维护 virtual_chunks 的动态计算
- **Agent Skill 层**：调用 ASTManager 的接口

---

### 7. 实现步骤（已确定）

1. **先实现一个最小化的 Parser**（只处理 H1-H6 和 Paragraph）
   - 验证 Stack-based Folding 的正确性
   - 测试标题回退和跳跃情况

2. **扩展到其他节点类型**（Code, Table, List）
   - 确保代码块内的 `#` 不会被误判为标题
   - 处理列表的嵌套结构

3. **实现虚拟分块**
   - 实现 8K tokens 阈值检测
   - 实现降级瀑布流切分策略
   - 实现虚拟分块的修改逻辑

4. **实现渲染器**
   - DFS 遍历 AST
   - 根据节点类型添加正确的换行符
   - 验证渲染结果的正确性

---

### 8. 关键优势总结

这种"扁平流 → 栈折叠成逻辑树 → 局部编辑 → 遍历拼接输出"的解析器架构：
- ✅ 能完美适配 Markdown 的特性
- ✅ 为嵌套 Agent 体系提供最坚实、最防弹的数据底层
- ✅ 避免了正则表达式的脆弱性
- ✅ 保证了原始 Markdown 的无损转换

---

## 七、 职责边界与入口判断机制（已确定）

> 本章节记录了 Markdown Skill 的职责边界划分和入口判断机制，确保系统只处理"编辑现有内容"的任务，不处理"创作新内容"的任务。

### 1. 核心原则：是否需要 Skill "原创"内容

**✅ 适合：用户提供内容**
```python
# 用户想要添加一个新章节，并且已经写好了内容
append_new_node(
    parent_id="root",
    content="这是新章节的内容",  # 用户提供的内容
    node_type="paragraph"
)
```

**❌ 不适合：Skill 需要创作**
```python
# 用户想要添加一个新章节，但没有提供内容，要求 Skill 创作
append_new_node(
    parent_id="root",
    content="写一个关于 AI 的介绍",  # 这是创作指令，不是内容
    node_type="paragraph"
)
```

---

### 2. "编辑" vs "创作" 的定义

#### 编辑（✅ 适合 Markdown Skill）

| 动作类型 | 示例 | 原因 |
|---------|------|------|
| 修改文本 | "把'旧系统'改为'遗留系统'" | 替换现有内容 |
| 删除内容 | "删除第三章的最后一段" | 删除现有内容 |
| 调整格式 | "调整第三章的结构" | 调整现有内容 |
| 提取信息 | "总结第二章的内容" | 提取现有信息 |
| 精简内容 | "把这段话压缩到 100 字" | 精简现有内容 |
| 查找内容 | "找到所有提到 AI 的段落" | 查找现有内容 |
| 修复错误 | "修正第三章的错别字" | 修改现有内容 |

**本质**：不增加新信息，只操作现有内容。

#### 创作（❌ 不适合 Markdown Skill）

| 动作类型 | 示例 | 原因 |
|---------|------|------|
| 扩写内容 | "把这段话扩写，加入更多细节" | 添加新内容 = 创作 |
| 补充内容 | "补充第三章的背景介绍" | 添加新内容 = 创作 |
| 从零创作 | "写一篇关于 AI 的文章" | 创作新内容 |
| 外部依赖 | "加入 2027 年的预测数据" | 需要外部信息 |
| 复杂构思 | "为这个项目设计一个技术方案" | 需要构思和规划 |
| 添加内容 | "在第三章结尾加一个总结" | 添加新内容 = 创作 |

**本质**：增加新信息，需要 Skill 创作或搜索。

---

### 3. 入口判断机制

**设计原则**：只在 `process_markdown` 入口判断一次，后面不再判断。

```python
class MarkdownManagerSkill:
    async def process_markdown(self, file_path: str, intention: str) -> str:
        """
        处理或编辑指定的 Markdown 文件。
        :param file_path: 文件路径
        :param intention: 自然语言描述的具体意图
        :return: 任务执行结果报告
        """

        # === 第一步：判断 intention 是否合适（只判断一次） ===
        is_appropriate, reason = await self._validate_intention(intention)

        if not is_appropriate:
            return f"""❌ 无法执行此任务：{reason}

提示：Markdown Skill 适用于**编辑现有内容**的任务，包括：
- 修改、替换、删除现有内容
- 调整格式、结构
- 总结、提取、查找现有信息
- 精简、压缩现有内容

不适合**创作新内容**的任务，如：
- 扩写、补充、添加新内容
- 从零创作文章
- 需要外部信息或知识的任务
"""

        # === 第二步：解析 Markdown 并创建 WorkerAgent ===
        ast_tree = await self._parse_markdown(file_path)
        worker = MarkdownWorkerAgent(ast_tree=ast_tree, intention=intention)

        # === 第三步：执行任务（WorkerAgent 内部不再判断） ===
        result = await worker.run()

        # === 第四步：保存修改 ===
        if ast_tree.is_dirty:
            await self._save_markdown(file_path, ast_tree)

        return result
```

---

### 4. _validate_intention 的实现

**关键设计**：
- 不读取文档内容，只根据 intention 本身判断
- 判断核心：是"编辑现有内容"还是"创作新内容"

```python
async def _validate_intention(self, intention: str) -> Tuple[bool, str]:
    """
    判断 intention 是否适合 Markdown Skill
    只根据 intention 本身判断，不读取文档内容

    :param intention: 用户的意图描述
    :return: (是否合适, 拒绝原因)
    """

    prompt = f"""
你是一个任务分类器，判断用户的意图是否适合"Markdown 文档编辑 Skill"。

【用户意图】
{intention}

=== 适合的任务类型（编辑现有内容） ===
✅ 修改文本：替换、删除现有内容
✅ 调整格式：调整结构、修复格式
✅ 提取信息：总结、查找、分析现有内容
✅ 精简内容：压缩、删减现有内容

=== 不适合的任务类型（创作新内容） ===
❌ 添加内容：扩写、补充、增加新段落
❌ 从零创作：写一篇文章、创作新章节
❌ 外部依赖：需要搜索最新数据、需要外部知识
❌ 复杂构思：需要设计结构、规划内容框架

=== 核心判断标准 ===
1. **编辑 vs 创作**：
   - 编辑 = 修改、删除、调整**现有**内容 → 适合
   - 创作 = 添加、扩写、补充**新**内容 → 不适合

2. **内源 vs 外源**：
   - 如果只需要文档内的信息 → 适合
   - 如果需要外部知识或数据 → 不适合

3. **关键动词识别**：
   - ✅ 修改、替换、删除、调整、整理、总结、提取、压缩
   - ❌ 写、创作、扩写、补充、添加、增加、设计、规划

=== 示例 ===
✅ "把第三章的'旧系统'改为'遗留系统'" → 适合（替换现有内容）
✅ "删除第三章的最后一段" → 适合（删除现有内容）
✅ "总结第二章的内容" → 适合（提取现有信息）
✅ "调整第三章的结构" → 适合（调整现有内容）
✅ "把这段话压缩到 100 字" → 适合（精简现有内容）

❌ "把这段话扩写，加入更多细节" → 不适合（扩写 = 添加新内容 = 创作）
❌ "为这个项目写一个介绍" → 不适合（创作新内容）
❌ "写一篇关于 AI 的文章" → 不适合（从零创作）
❌ "加入 2027 年的预测数据" → 不适合（需要外部信息）
❌ "补充第三章的背景介绍" → 不适合（补充新内容 = 创作）

请以 JSON 格式返回：
{{
    "is_appropriate": true/false,
    "reason": "判断理由（如果不适合，说明原因；如果适合，说明任务类型）"
}}
"""

    # 调用 LLM
    response = await self._call_llm_directly(prompt)
    result = json.loads(response)

    return result["is_appropriate"], result["reason"]
```

---

### 5. 更新后的底层 action 设计

#### MarkdownASTCoreSkill 的 actions（原子编辑动作）

```python
class MarkdownASTCoreSkill:

    # === 导航与定位 ===
    async def get_toc(self, depth: int = 2) -> str:
        """获取文档层级大纲及 node_id"""
        pass

    async def search_keywords(self, query: str, context_lines: int = 2) -> str:
        """全文关键字/正则扫描，返回命中列表"""
        pass

    # === 精准阅读 ===
    async def read_node_content(self, node_id: str) -> str:
        """拉取具体节点内容"""
        pass

    # === 编辑（修改现有内容） ===
    async def exact_replace(self, node_id: str, old_str: str, new_str: str) -> str:
        """
        精确替换文本
        :param old_str: 原文
        :param new_str: 新内容（用户提供）
        """
        pass

    async def modify_node(self, node_id: str, edit_instruction: str) -> str:
        """
        修改节点内容（改写表述方式）
        :param edit_instruction: 修改指令（如"把'旧系统'改为'遗留系统'"）

        注意：虽然参数叫 instruction，但实际上只接受"修改现有内容"的指令，
        不接受"添加新内容"的指令（如"扩写，加入更多细节"）
        """
        pass

    async def delete_node(self, node_id: str) -> str:
        """删除节点"""
        pass

    # === 添加（用户提供内容） ===
    async def append_new_node(self, parent_id: str, content: str, node_type: str = "paragraph") -> str:
        """
        在父节点后追加新节点
        :param content: 新节点的内容（用户提供）
        :param node_type: 节点类型（如 "h1", "h2", "paragraph", "code_block"）
        """
        pass

    async def insert_node(self, after_node: str, content: str, node_type: str = "paragraph") -> str:
        """
        在指定节点后插入新节点
        :param after_node: 在哪个节点后插入（node_id）
        :param content: 新节点的内容（用户提供）
        :param node_type: 节点类型
        """
        pass

    # === 总结（提取现有信息） ===
    async def summarize_node(self, node_id: str) -> str:
        """总结节点内容（提取现有信息）"""
        pass

    async def summarize_document(self) -> str:
        """总结整个文档（提取现有信息）"""
        pass
```

---

### 6. 参数设计的关键区别

#### content vs instruction

| 参数类型 | 含义 | 示例 | 是否适合 |
|---------|------|------|---------|
| `content` | 用户提供的内容 | `content="这是新段落"` | ✅ 适合 |
| `instruction`（修改类） | 修改现有内容的指令 | `instruction="把A改为B"` | ✅ 适合 |
| `instruction`（创作类） | 需要创作的指令 | `instruction="写一个介绍"` | ❌ 不适合 |

#### 实际例子

**✅ 适合（用户提供内容）**
```python
# 用户想要添加一个新章节，并且已经写好了内容
append_new_node(
    parent_id="root",
    content="## 第四章\n\n这是第四章的内容",
    node_type="h2"
)
```

**❌ 不适合（需要创作）**
```python
# 用户想要添加一个新章节，但没有提供内容，要求 Skill 创作
# 这种情况下，入口的 _validate_intention 应该拒绝
```

---

### 7. WorkerAgent 如何处理复杂任务

#### 场景：用户要求"搜索并添加"

**用户意图**："搜索 2027 年的 AI 预测数据，然后添加到第三章"

**入口判断**：
```
❌ 不适合（需要搜索 + 创作）
```

**错误提示**：
```
❌ 无法执行此任务：这个任务需要搜索外部信息并创作新内容。

建议：如果需要先搜索信息，请在外层先调用 web_search，然后再调用 Markdown Skill 进行编辑。
```

**正确的做法（外层编排）**：

```python
# BaseAgent 或上层 Agent 的编排逻辑
async def handle_complex_task():
    # Step 1: 搜索信息
    search_result = await call_skill(
        skill_name="simple_web_search",
        action="web_search",
        params={"purpose": "2027年AI预测数据", "max_time": 5}
    )

    # Step 2: 基于搜索结果，生成内容
    new_content = await call_llm(
        prompt=f"""
        基于以下搜索结果，为第三章写一个关于 2027 年 AI 预测的段落：

        {search_result}
        """
    )

    # Step 3: 调用 Markdown Skill 添加内容
    result = await call_skill(
        skill_name="markdown",
        action="append_new_node",
        params={
            "parent_id": "root/h1_3",
            "content": new_content,
            "node_type": "paragraph"
        }
    )
```

---

### 8. 关键设计决策总结

1. **职责边界清晰**：
   - ✅ Markdown Skill 只处理"编辑现有内容"
   - ❌ 不处理"创作新内容"或"需要外部信息"的任务

2. **入口判断一次**：
   - 只在 `process_markdown` 入口判断
   - WorkerAgent 执行过程中不再判断

3. **用户提供内容**：
   - `append_new_node` 和 `insert_node` 接受 `content` 参数（用户提供）
   - 不接受需要 Skill 创作的 `instruction` 参数

4. **命名更明确**：
   - `rewrite_node` → `modify_node`（更明确是"修改"而非"重写"）
   - 新增 `insert_node`（在指定位置插入）

5. ** summarize_node 的边界**：
   - 暂时不管 corner case（如"总结并给出建议"）
   - 因为只是额外输出内容，不涉及 markdown 本身的变化

---

## 八、 最终架构实现方案（已确定）

> 本章节记录了最终的架构实现方案，包括 Skill 挂载机制、file_path 管理、WorkerAgent 创建等关键设计。

### 1. 两层 MicroAgent 架构

```
外层 MicroAgent (MarkdownManagerSkillMixin)
├─ 只有一个 action: process_markdown(file_path, intention)
├─ 职责：
│   1. validate intention
│   2. 如果 OK，创建内层 MicroAgent
└─ 不负责具体的编辑逻辑

内层 MicroAgent (MarkdownSkillMixin)
├─ 有多个 actions: get_toc, search_keywords, read_node_content, modify_node 等
├─ 被配置了 MarkdownSkill（所以有这些能力）
├─ 接收：intention + file_path
├─ 自己计划：先做什么后做什么
└─ 通过 MarkdownSkillMixin._get_ast() 获取 AST（第一次调用时生成）
```

---

### 2. Skill 挂载机制

**MicroAgent 创建时**：
```python
worker = MicroAgent(
    parent=self.root_agent,
    name="MarkdownWorkerAgent",
    available_skills=["markdown"]  # ← 指定 skill 名称
)
```

**_create_dynamic_class 的工作流程**：
1. 从 SKILL_REGISTRY 加载 `markdown` skill 的 Mixin 类
2. 使用 `type()` 动态创建新类：`class DynamicAgent(MicroAgent, MarkdownSkillMixin)`
3. 替换 `self.__class__`
4. 扫描所有 `@register_action` 方法

**结果**：worker 实例现在有了 MarkdownSkillMixin 的所有方法

---

### 3. file_path 的管理（关键设计）

**设计原则**：WorkerAgent 从头到尾只处理一个文件，所以 file_path 只需要设置一次。

**实现方案**：

```python
# MarkdownManagerSkillMixin.process_markdown

# 创建 WorkerAgent
worker = MicroAgent(
    parent=self.root_agent,
    name="MarkdownWorkerAgent",
    available_skills=["markdown"]
)

# 🔑 设置当前处理的文件路径（动态设置属性）
worker.current_file_path = file_path

# 执行任务（在 task 中也明确提到文件路径）
result = await worker.execute(
    run_label=f"markdown_task_{int(time.time())}",
    persona=self._build_worker_persona(),
    task=f"""请处理以下 Markdown 文件：

文件路径：{file_path}

任务：{intention}

【工作流程】
1. 先调用 get_toc() 查看文档结构
2. 调用相关 actions 完成任务
3. 完成后调用 save_markdown() 保存文件
4. 最后调用 all_finished() 返回结果
""",
    max_steps=50,
    max_time=5,
    simple_mode=True
)
```

**在 MarkdownSkillMixin 中访问**：

```python
class MarkdownSkillMixin:
    """Markdown Skill - 提供 Markdown 文档编辑能力"""

    def _get_current_file_path(self) -> str:
        """获取当前处理的文件路径"""
        # 通过 self.current_file_path 访问（在 WorkerAgent 上动态设置的属性）
        if hasattr(self, 'current_file_path'):
            return self.current_file_path
        raise ValueError("current_file_path 未设置")

    def _get_ast(self) -> MarkdownAST:
        """获取或创建 AST（第一次调用时解析，后续直接返回缓存）"""
        file_path = self._get_current_file_path()

        if not hasattr(self, '_ast'):
            self._ast = None

        if self._ast is None:
            parser = MarkdownParser()
            self._ast = parser.parse(file_path)
            self.logger.info(f"✅ 解析 Markdown: {file_path}")

        return self._ast
```

**验证**：
```python
# 测试动态属性设置
class MicroAgent:
    def __init__(self, name):
        self.name = name

class SkillMixin:
    def get_file_path(self):
        return self.current_file_path

# 动态组合
class DynamicAgent(MicroAgent, SkillMixin):
    pass

# 测试
agent = DynamicAgent("test")
agent.current_file_path = "/tmp/test.md"  # ← 动态设置属性
print(agent.get_file_path())  # ✅ 输出: /tmp/test.md
```

**结论**：动态设置属性是可行的，在 Skill Mixin 的方法中可以通过 `self.current_file_path` 访问。

---

### 4. MarkdownSkillMixin 的完整实现

```python
# src/agentmatrix/skills/markdown/skill.py

class MarkdownSkillMixin:
    """Markdown Skill - 提供 Markdown 文档编辑能力"""

    # === 私有方法 ===

    def _get_current_file_path(self) -> str:
        """获取当前处理的文件路径"""
        if hasattr(self, 'current_file_path'):
            return self.current_file_path
        raise ValueError("current_file_path 未设置")

    def _get_ast(self) -> MarkdownAST:
        """获取或创建 AST"""
        file_path = self._get_current_file_path()

        if not hasattr(self, '_ast'):
            self._ast = None

        if self._ast is None:
            parser = MarkdownParser()
            self._ast = parser.parse(file_path)
            self.logger.info(f"✅ 解析 Markdown: {file_path}")

        return self._ast

    # === Actions（都不需要 file_path 参数）===

    @register_action(
        "获取 Markdown 文档的目录结构",
        param_infos={
            "depth": "目录深度（默认 2）"
        }
    )
    async def get_toc(self, depth: int = 2) -> str:
        """获取文档目录"""
        ast = self._get_ast()
        return ast.get_toc(depth)

    @register_action(
        "在 Markdown 文档中搜索关键字",
        param_infos={
            "query": "搜索关键词",
            "context_lines": "上下文行数（默认 2）"
        }
    )
    async def search_keywords(self, query: str, context_lines: int = 2) -> str:
        """搜索关键字"""
        ast = self._get_ast()
        return ast.search_keywords(query, context_lines)

    @register_action(
        "读取 Markdown 节点的内容",
        param_infos={
            "node_id": "节点 ID（如 root/h1_1/h2_2/p_3）"
        }
    )
    async def read_node_content(self, node_id: str) -> str:
        """读取节点内容"""
        ast = self._get_ast()
        return ast.get_node(node_id).content

    @register_action(
        "修改 Markdown 节点的内容",
        param_infos={
            "node_id": "节点 ID",
            "edit_instruction": "修改指令（如'把A改为B'）"
        }
    )
    async def modify_node(self, node_id: str, edit_instruction: str) -> str:
        """修改节点内容"""
        ast = self._get_ast()
        node = ast.get_node(node_id)

        # 调用 LLM 修改
        modified_content = await self._rewrite_with_llm(node.content, edit_instruction)

        # 更新 AST
        node.content = modified_content
        node.is_dirty = True

        return f"已修改节点 {node_id}"

    @register_action(
        "精确替换文本",
        param_infos={
            "node_id": "节点 ID",
            "old_str": "原文",
            "new_str": "新内容"
        }
    )
    async def exact_replace(self, node_id: str, old_str: str, new_str: str) -> str:
        """精确替换"""
        ast = self._get_ast()
        node = ast.get_node(node_id)

        if old_str not in node.content:
            return f"错误：'{old_str}' 不在节点 {node_id} 中"

        node.content = node.content.replace(old_str, new_str)
        node.is_dirty = True

        return f"已替换节点 {node_id} 中的文本"

    @register_action(
        "追加新节点",
        param_infos={
            "parent_id": "父节点 ID",
            "content": "新节点的内容",
            "node_type": "节点类型（如 h1, h2, paragraph, code_block）"
        }
    )
    async def append_new_node(self, parent_id: str, content: str, node_type: str = "paragraph") -> str:
        """追加新节点"""
        ast = self._get_ast()
        parent_node = ast.get_node(parent_id)

        # 创建新节点
        new_node = MarkdownNode(
            node_id=ast.generate_node_id(parent_id),
            node_type=node_type,
            content=content
        )

        parent_node.children.append(new_node)
        new_node.is_dirty = True

        return f"已追加节点 {new_node.node_id}"

    @register_action(
        "插入新节点",
        param_infos={
            "after_node": "在哪个节点后插入（node_id）",
            "content": "新节点的内容",
            "node_type": "节点类型"
        }
    )
    async def insert_node(self, after_node: str, content: str, node_type: str = "paragraph") -> str:
        """插入新节点"""
        ast = self._get_ast()
        after_node_obj = ast.get_node(after_node)
        parent = ast.get_parent(after_node_obj)

        # 创建新节点
        new_node = MarkdownNode(
            node_id=ast.generate_node_id(parent.node_id),
            node_type=node_type,
            content=content
        )

        # 插入到指定位置
        index = parent.children.index(after_node_obj)
        parent.children.insert(index + 1, new_node)
        new_node.is_dirty = True

        return f"已插入节点 {new_node.node_id}"

    @register_action(
        "删除节点",
        param_infos={
            "node_id": "要删除的节点 ID"
        }
    )
    async def delete_node(self, node_id: str) -> str:
        """删除节点"""
        ast = self._get_ast()
        node = ast.get_node(node_id)
        parent = ast.get_parent(node)

        parent.children.remove(node)

        return f"已删除节点 {node_id}"

    @register_action(
        "总结节点内容",
        param_infos={
            "node_id": "节点 ID"
        }
    )
    async def summarize_node(self, node_id: str) -> str:
        """总结节点内容"""
        ast = self._get_ast()
        node = ast.get_node(node_id)

        # 调用 LLM 总结
        summary = await self._summarize_with_llm(node.content)

        return summary

    @register_action(
        "保存 Markdown 文件的修改",
        param_infos={}
    )
    async def save_markdown(self) -> str:
        """保存修改"""
        file_path = self._get_current_file_path()
        ast = self._get_ast()

        # 渲染 AST 为 Markdown
        renderer = MarkdownRenderer()
        content = renderer.render(ast.root_node)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 清除 dirty 标记
        ast.clear_dirty_flags()

        return f"已保存 {file_path}"
```

---

### 5. MarkdownManagerSkillMixin 的完整实现

```python
# src/agentmatrix/skills/markdown_manager/skill.py

class MarkdownManagerSkillMixin:
    """Markdown Manager Skill - 入口，负责验证和创建内层 MicroAgent"""

    @register_action(
        "处理或编辑指定的 Markdown 文件",
        param_infos={
            "file_path": "Markdown 文件路径",
            "intention": "自然语言描述的具体意图"
        }
    )
    async def process_markdown(self, file_path: str, intention: str) -> str:
        """处理或编辑指定的 Markdown 文件"""

        # === 第一步：验证 intention ===
        is_appropriate, reason = await self._validate_intention(intention)

        if not is_appropriate:
            return f"""❌ 无法执行此任务：{reason}

提示：Markdown Skill 适用于**编辑现有内容**的任务，包括：
- 修改、替换、删除现有内容
- 调整格式、结构
- 总结、提取、查找现有信息
- 精简、压缩现有内容

不适合**创作新内容**的任务，如：
- 扩写、补充、添加新内容
- 从零创作文章
- 需要外部信息或知识的任务
"""

        # === 第二步：创建内层 MicroAgent ===
        worker = MicroAgent(
            parent=self.root_agent,
            name="MarkdownWorkerAgent",
            available_skills=["markdown"]  # ← 配置 markdown skill
        )

        # 🔑 设置当前处理的文件路径
        worker.current_file_path = file_path

        # === 第三步：执行任务 ===
        result = await worker.execute(
            run_label=f"markdown_task_{int(time.time())}",
            persona=self._build_worker_persona(),
            task=f"""请处理以下 Markdown 文件：

文件路径：{file_path}

任务：{intention}

【工作流程】
1. 先调用 get_toc() 查看文档结构
2. 调用相关 actions 完成任务
3. 完成后调用 save_markdown() 保存文件
4. 最后调用 all_finished() 返回结果
""",
            max_steps=50,
            max_time=5,
            simple_mode=True
        )

        # === 第四步：处理结果 ===
        if isinstance(result, dict) and "error" in result:
            return f"❌ 任务执行失败：{result['error']}"

        # 🔑 安全网：如果 WorkerAgent 忘记保存，自动保存
        if hasattr(worker, '_ast') and worker._ast and worker._ast.has_dirty_nodes():
            self.logger.warning("⚠️ WorkerAgent 未保存文件，自动保存...")
            await worker.save_markdown()
            return f"{result}\n\n（注：文件已自动保存）"

        return result or "任务已完成"

    async def _validate_intention(self, intention: str) -> Tuple[bool, str]:
        """验证 intention 是否适合（见第七章）"""
        # ... (实现见第七章)
        pass

    def _build_worker_persona(self) -> str:
        """构建 WorkerAgent 的 persona"""
        return """
你是一个专业的 Markdown 文档处理引擎。

【工作规范】
1. 在修改任何东西前，必须先进行"调查"：
   - 调用 get_toc() 查看文档骨架
   - 调用 search_keywords() 搜索关键字
   - 调用 read_node_content() 读取节点内容

2. 修改完成后，必须调用 save_markdown() 保存文件

3. 任务完成后，调用 all_finished() 返回结果

【可用工具】
- get_toc: 获取目录
- search_keywords: 搜索关键字
- read_node_content: 读取节点
- modify_node: 修改节点
- exact_replace: 精确替换
- append_new_node: 追加新节点
- insert_node: 插入新节点
- delete_node: 删除节点
- summarize_node: 总结节点
- save_markdown: 保存文件
"""
```

---

### 6. 关键设计优势

**1. 所有 action 都不需要 file_path 参数**
- WorkerAgent 从头到尾只处理一个文件
- file_path 在创建时设置一次，所有 action 共享

**2. AST 的懒加载和缓存**
- 第一次调用 action 时解析 Markdown
- 后续 action 直接使用缓存
- WorkerAgent 销毁时缓存自动清理

**3. 自动保存机制（安全网）**
- WorkerAgent 被要求显式调用 save_markdown()
- 如果忘记，process_markdown 会自动保存
- 防止丢失修改

**4. 简洁的接口**
- 外层只有一个入口：process_markdown(file_path, intention)
- 内层有多个原子化的 actions
- 职责清晰，易于理解和维护

---

### 7. 目录结构

```
src/agentmatrix/skills/
├── markdown_manager/
│   ├── __init__.py
│   └── skill.py          # MarkdownManagerSkillMixin
├── markdown/
│   ├── __init__.py
│   ├── skill.py          # MarkdownSkillMixin
│   ├── parser.py         # MarkdownParser
│   ├── renderer.py       # MarkdownRenderer
│   └── ast.py            # MarkdownNode, MarkdownAST
└── registry.py           # SKILL_REGISTRY（已有）
```

---

### 8. 已确定的设计清单

✅ **AST 解析器**（第六章）
- 技术选型：markdown-it-py
- 四阶段 Pipeline
- Stack-based Folding
- 虚拟分块（8K tokens）

✅ **职责边界**（第七章）
- 编辑 vs 创作的划分
- 入口判断机制
- content vs instruction 参数

✅ **WorkerAgent 控制**（使用 MicroAgent 内置机制）
- max_steps: 50
- max_time: 5 分钟
- 自动终止

✅ **架构实现**（第八章）
- 两层 MicroAgent
- Skill 挂载机制
- file_path 管理
- 自动保存机制

---

## 下一步：开始实现

所有架构设计已经确定，可以开始实现了：

1. **第一阶段**：实现 AST 解析器（Parser）
   - 最小化版本（只处理 H1-H6 和 Paragraph）
   - 验证 Stack-based Folding

2. **第二阶段**：实现 MarkdownSkillMixin
   - 所有 actions
   - AST 管理
   - LLM 调用

3. **第三阶段**：实现 MarkdownManagerSkillMixin
   - 入口判断
   - WorkerAgent 创建
   - 自动保存

4. **第四阶段**：集成测试
   - 端到端测试
   - 边界情况测试