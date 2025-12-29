这份文档总结了我们关于 **知识整理和报告编写** 系统的最终架构设计。
---

# 系统设计文档：Report Writer (Deep Research Pipeline)

## 1. 设计哲学与核心原则

*   **LLM as a Function (非多智能体博弈)**：系统不采用复杂的多Agent通信模式，而是采用**状态机（State Machine）**模式。LLM 被视为一个无状态的变换函数，通过 Python 代码维护全局状态（Context）。
*   **贝叶斯知识更新 (Bayesian Inference Flow)**：流程遵循“先验（常识） -> 采样修正（校准） -> 全量验证（执行）”的逻辑，利用 LLM 的内部知识降低搜索空间，再通过文档修正特异性。
*   **双通道架构 (Dual-Channel Architecture)**：
    *   **事实流 (Fact Stream)**：维护一份结构化的 Markdown 笔记（Concept Notes），负责准确性、定义和实体关系。
    *   **叙事流 (Narrative Stream)**：维护一份文章草稿（Draft），负责逻辑结构、可读性和对大纲的填充。
*   **自然语言优先 (No-JSON Policy)**：内部数据交换（尤其是笔记和草稿）全部使用 Markdown 格式，利用 LLM 对文本层级的理解力，避免 JSON 语法错误的脆弱性。

* **基本假设**: 日常一般工作的report编写（不是编字典，不是编教材，不是写大书），并不会涉及特别多的新concept/term，最终产品往往是几页内容，很少几十页。涉及的专业概念、特殊事实，很少会超过几百条。基于这一假设，尽管需要处理的原始文本原料可能是相当大量，但是整理出来的concept notes/table, 以及working draft + blueprint + 额外prompt，再加上LLM输出的改进draft，很可能是可以在几十K的context window内安全存放的。—— 这个假设是否成立，需要仔细review。

## 2. 核心数据结构 (The State)

在整个生命周期中，内存中维护一个唯一的 `ResearchState` 对象，在各个处理函数间流转：

```python
@dataclass
class ResearchState:
    goal: str                  # 研究目标
    blueprint: str = ""        # 调查蓝图（大纲、核心问题清单、预设章节）
    concept_notes: str = ""    # 概念笔记（Markdown格式，包含实体定义、关系、来源）
    draft_content: str = ""    # 正文草稿（Markdown格式，分章节填充的内容）
    processed_files: List[str] # 进度记录
```

## 3. 处理流程 (Pipeline Phases)

整个对外接口为一个异步函数 `write_report`，内部串联四个阶段：

### Phase 0: The Theorist (先验生成)
*   **目的**：冷启动，利用 LLM 训练数据建立初始认知。
*   **输入**：`main_subject`, `main_purpose`
*   **说明**：main_subject类似于主题、标题，是用户核心希望的东西。main_purpose包括了用户的一些想法、需求、想解决的问题等等
*   **动作**：LLM 根据常识生成一份 **Generic Blueprint (通用蓝图)**。包含标准章节、通常需要关注的概念、潜在的研究问题。
*   **输出**：初始 `blueprint`。

### Phase 1: The Scout (侦察与校准)
*   **目的**：消除幻觉，根据实际数据修正蓝图。
*   **输入**：初始 `blueprint` + 随机采样的 3-5 个文档片段。
*   **动作 (Async Parallel)**：
    *   并行调用 LLM 阅读每个样本，对比蓝图，生成 **Delta Report**（指出蓝图中多余的部分、缺失的特异性主题）。
    *   **主编合成 (Synthesis)**：汇总 Delta Reports，生成 **Specific Blueprint (专用蓝图)**。
*   **输出**：修正后的 `blueprint` (定型的目录结构和问题清单)。

### Phase 2: The Execution Loop (全量迭代)
*   **目的**：流式阅读所有文档，填肉。
*   **输入**：`blueprint` + 文档流 (Chunk Stream)。
*   **动作 (Sequential Loop)**：
    对每个文档块（Batch），依次执行两个操作：
    1.  **Step A - Update Notes (知识库更新)**：
        *   读取 `current_notes` 和 `new_text`。
        *   识别新实体/新定义，或更新旧实体的属性/关系。
        *   **输出**：更新后的 `concept_notes`。
    2.  **Step B - Update Draft (叙事填充)**：
        *   读取 `blueprint` (只读参考), `current_draft`, `current_notes` (辅助), `new_text`。
        *   判断 `new_text` 是否回答了 `blueprint` 中的问题或属于某章节。
        *   将内容整合进 `draft`，保留引用来源，不删除已有事实。
        *   **输出**：更新后的 `draft_content`。

### Phase 3: The Finalizer (终稿润色)
*   **目的**：统一文风，整合附件。
*   **输入**：`draft_content` + `concept_notes`。
*   **动作**：
    *   润色正文，检查逻辑连贯性。
    *   基于 `concept_notes` 生成附录（Glossary/Terminology）。
*   **输出**：**Final Report**。

## 4. 技术实现规范

*   **语言/框架**：Python, `asyncio`。
*   **代码模式**：Mixin 模式（混入到主 Agent 类中）。
*   **IO 处理**：
    *   **Document Stream Generator**：封装底层文件读取逻辑，屏蔽 `.md/.txt/.pdf` 差异，提供统一的 `yield chunk` 接口。
    *   **Checkpointing**：每个阶段结束时将 State 保存为 Markdown 文件，便于调试和断点恢复。
*   **Prompt 策略**：
    *   使用 Markdown Heading (`#`, `##`) 引导 LLM 的注意力。
    *   在 Draft 更新阶段，明确“增量更新”指令，防止遗忘旧内容。

