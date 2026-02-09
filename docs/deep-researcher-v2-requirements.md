# Deep Researcher V2 需求分析与设计

## 一、设计目标：从"控制驱动"到"自主驱动"

### V1 的核心特征
```
Python 控制 → 状态机 → 结构化数据 → LLM 执行
    ↓
复杂的流程控制代码
```

### V2 的核心特征
```
LLM 自主决策 → 简单的信息结构 → 强大的工具
    ↓
极简的编排代码
```

---

## 二、架构设计

### 2.1 基础原则

- **Micro Agent Pattern**：保持不变
- **Action 调用机制**：保持不变
- **Brain 接口**：保持不变

### 2.2 阶段划分简化

**V1**：Planning Stage → Research Loop → Writing Loop

**V2**：单一 Micro Agent 执行（不划分阶段）

**理由**：
- Planning 本质上就是更新 dashboard
- Research 阶段同样需要更新 dashboard（改计划等）
- LLM 自主决定何时做什么

---

## 三、核心能力设计

### 3.1 文件操作能力（高优先级）

#### 设计思路：统一接口 + File Micro Agent

**主 Agent 侧**：

只提供一个简单的 action：
```python
file_operation(operation_description: str) -> str
```

**示例调用**：
```
主 Agent: "我需要读取 overall_dashboard.md 的研究蓝图章节"
→ file_operation("读取 overall_dashboard.md 中'研究蓝图'章节的内容")

主 Agent: "我需要在 notebook 中新增一个章节"
→ file_operation("在 Notebook 目录下创建'第四章 数据分析.md'，内容为...")

主 Agent: "我要搜索所有 note 文件中包含'机器学习'的内容"
→ file_operation("在 Notebook 目录下搜索包含'机器学习'的所有文件")
```

#### File Micro Agent 职责

**内部实现**：
```
FUNCTION file_operation(operation_description):
    # 启动 File Micro Agent
    RUN_MICRO_AGENT(
        task=f"""
        用户要求执行文件操作：{operation_description}

        请解析用户意图，执行相应的操作。

        你可以使用以下具体 actions：
        - read_file
        - write_file
        - create_file
        - search_in_file
        - grep_files
        - stream_read_file
        - list_directory
        - delete_file
        ... (更多文件操作)
        """,

        available_actions=[
            # 所有具体的文件操作 actions 在这一层注册
            "read_file",
            "write_file",
            "create_file",
            "search_in_file",
            "grep_files",
            "stream_read_file",
            "list_directory",
            "delete_file",
            # ...
        ],

        max_steps=10
    )
```

**优势**：
1. **降低主 Agent 认知负担**：不需要知道 10+ 个文件操作 actions
2. **灵活扩展**：新增文件操作只需在 File Micro Agent 中注册
3. **更好的意图理解**：File Micro Agent 可以理解自然语言描述
4. **专业化**：File Micro Agent 专注于文件操作，prompt 更优化

#### 具体文件操作 Actions（待 File Micro Agent 内部使用）

**基础操作**：
```
read_file(file_path, mode="full")
    - mode="full": 全部内容
    - mode="lines": 行范围（如 lines="1-100"）
    - mode="stream": 流式读取

write_file(file_path, content, mode="overwrite")
    - mode="overwrite": 覆盖
    - mode="append": 追加
    - mode="insert": 插入

create_file(file_path, initial_content="")
```

**搜索和查找**：
```
search_in_file(file_path, pattern, context_lines=0)
    - 在文件中搜索
    - 返回匹配行及上下文

grep_files(pattern, directory, options="")
    - 调用 grep 命令
    - 支持正则

file_search(directory, name_pattern)
    - 搜索文件名
```

**流式读取大文件**：
```
stream_read_file(file_path, chunk_size=1000)
    - 分批返回
    - 每次 chunk_size 行

continue_stream_read(stream_id)
    - 继续读取下一批
```

**目录操作**：
```
list_directory(directory_path)
    - 列出目录内容

create_directory(directory_path)
    - 创建目录

delete_file(file_path)
    - 删除文件
```

### 3.2 文件操作实现方式（待研究）

#### 选项 1：Python 代码实现

**方式**：自己编写 Python 函数实现每个文件操作

**优势**：
- 完全控制
- 跨平台兼容
- 错误处理可控

**劣势**：
- 需要大量代码
- 重复造轮轮

**适用**：
- 简单操作（read, write, create）
- 需要精细控制的场景

#### 选项 2：调用 OS CLI

**方式**：通过 `subprocess` 调用系统命令

```python
import subprocess

def grep_files(pattern, directory):
    result = subprocess.run(
        ["grep", "-r", pattern, directory],
        capture_output=True,
        text=True
    )
    return result.stdout
```

**优势**：
- 利用成熟工具（grep, find, awk 等）
- 功能强大
- 代码简洁

**劣势**：
- 平台依赖（Linux vs Windows）
- 错误处理复杂
- 安全性考虑（命令注入）

**适用**：
- 复杂搜索和处理
- Linux 环境

#### 选项 3：Terminal 访问权限

**方式**：给 File Micro Agent 直接访问 terminal 的能力

```python
# 在 File Micro Agent 中提供
@register_action
async def execute_command(command: str) -> str:
    """执行 shell 命令"""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout
```

**优势**：
- 最大灵活性
- File Micro Agent 自主决定如何操作
- 无需预先定义所有操作

**劣势**：
- 安全风险高
- 错误难以控制
- 可预测性差

**适用**：
- 沙箱环境
- 受限场景

#### 选项 4：使用现成库

**候选库**：
- **Pathlib**：Python 标准库，路径操作
- **Watchdog**：文件监控
- **PyFilesystem2**：统一文件系统接口
- **AIOFiles**：异步文件操作

**优势**：
- 成熟稳定
- 功能完善
- 社区支持

**劣势**：
- 可能过度工程
- 学习成本

**适用**：
- 复杂文件系统操作
- 需要跨平台兼容

#### 推荐方案：混合模式

```
简单操作：Python 代码实现
    - read_file, write_file, create_file
    - 使用 pathlib + aiofiles

复杂操作：调用 OS CLI（带安全检查）
    - grep_files, search_in_file
    - 使用 subprocess + 参数校验

高级场景：Terminal 访问（受限）
    - 仅在沙箱环境
    - 白名单命令
```

### 3.3 Notebook 简化设计

**V1**：JSON 结构 + 复杂数据模型

**V2**：
```
Notebook/
├── 第一章 研究背景.md
├── 第二章 文献综述.md
├── 第三章 研究方法.md
└── ...
```

**核心规则**：
- 一个章节 = 一个 note 文件
- 格式不限制（让 LLM 自己决定）
- LLM 通过 `file_operation` 操作

**示例**：
```
主 Agent: "记录一条笔记到第一章"
→ file_operation("在 Notebook/第一章 研究背景.md 中追加：xxx研究发现...")

主 Agent: "查看第二章的所有笔记"
→ file_operation("读取 Notebook/第二章 文献综述.md 的全部内容")
```

### 3.4 Web 能力

**保留**：
```
web_search(query)  # 保持不变
```

**改进**：
```
visit_url(url)  # 从 download 改为 read
    - V1: download HTML 文件
    - V2: 直接阅读并返回内容
    - 可以使用 web_reader MCP
```

**Browser 能力（优先级稍后）**：
引入 **browser-use**，提供新的 action（待设计）

---

## 四、Context 管理（核心机制）

### 4.1 会话初始状态

**每一轮开始**：
```
System Prompt +
Overall Dashboard 内容 +
Current Dashboard 内容
```

**System Prompt 包含**：
- 文件规则（notebook 组织、dashboard 规则等）
- 写作规则
- 草稿规则
- 其他系统级指导

### 4.2 Action 执行与历史维护

**常规流程**：
```
LLM 决策 → 调用 Action → Action 返回结果 → Append 到 message history
```

**关键特性**：
- Action 内部 Micro Agent context 不污染主 context
- Action 结果作为普通消息 append

### 4.3 Context 压缩机制

**触发条件**：Brain 更新任一 Dashboard 时

**压缩逻辑**：
```
更新前：
    Message History = [msg1, msg2, ..., msgN]

更新 Dashboard：
    1. 读取对话历史
    2. 总结压缩到 Dashboard
    3. 更新 Dashboard 文件

更新后：
    Message History = [System Prompt, Overall Dashboard, Current Dashboard]
    之前的历史全部丢弃
```

**为什么可以丢弃**：
- Dashboard 是对话的压缩总结
- 之前信息已被提炼到 Dashboard
- 保留历史只会浪费 tokens

### 4.4 LLM 自主决策

**压缩后开始新会话**：
```
System Prompt: 文件规则、写作规则等
Message 1: Overall Dashboard
Message 2: Current Dashboard
```

**LLM 自主决定**：
- 阅读两个 Dashboard
- 根据当前状态决定下一步
- 不需要 Python loop 查找任务

### 4.5 终止条件

**LLM 完成后**：
```
LLM 调用: all_finished(result="研究报告已生成：{path}")
```

---

## 五、完整工作流程

```
FUNCTION deep_research_v2(research_title, research_purpose):

    # Step 1: 初始化
    CREATE overall_dashboard.md
    CREATE current_dashboard.md
    CREATE Notebook/ directory

    # Step 2: 构建 System Prompt
    system_prompt = BUILD_SYSTEM_PROMPT(rules=[
        "文件规则：一个章节一个 note 文件",
        "Dashboard 更新会触发 context 压缩",
        "写作规则：...",
    ])

    # Step 3: 启动统一 Micro Agent
    RUN_MICRO_AGENT(
        task=f"""
        研究主题：{research_title}
        研究目的：{research_purpose}

        请自主完成：
        1. 制定研究蓝图
        2. 执行研究任务
        3. 撰写研究报告
        4. 完成后调用 all_finished

        你可以使用：
        - file_operation（所有文件操作）
        - web_search, visit_url
        - update_overall_dashboard
        - update_current_dashboard
        - all_finished
        """,

        system_prompt=system_prompt,

        initial_messages=[
            overall_dashboard_content,
            current_dashboard_content
        ],

        available_actions=[
            # 核心操作（极简集合）
            "file_operation",  # 所有文件操作
            "web_search",
            "visit_url",
            "update_overall_dashboard",  # 触发压缩
            "update_current_dashboard",   # 触发压缩
            "all_finished"
        ],

        max_steps=100,

        on_dashboard_update=COMPRESS_CONTEXT
    )

    RETURN final_report_path
```

---

## 六、待研究问题

### 6.1 文件操作实现方式

**问题**：具体文件操作方法如何实现？

**选项**：
1. Python 代码实现
2. 调用 OS CLI
3. 给 File Micro Agent terminal 访问权限
4. 使用现成库（pathlib, aiofiles, pyfilesystem2 等）

**状态**：待研究，暂无答案

**建议**：混合模式
- 简单操作：Python 代码
- 复杂操作：OS CLI（带安全检查）
- 特殊场景：受限 terminal 访问

### 6.2 Browser 集成（优先级稍后）

- browser-use 的具体集成方式
- Action 接口设计
- 与 web_search 的配合

### 6.3 大文件流式读取

- stream_read 的具体实现
- 如何让 LLM 理解"继续读取"
- 批次大小最佳实践

### 6.4 Dashboard 格式规范

- Overall Dashboard 的章节结构
- Current Dashboard 的章节结构
- 如何确保 LLM 遵循格式

