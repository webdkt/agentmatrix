# 11 — Prompt 设计深度对比

## System Prompt 组装结构

### AgentMatrix: 模板驱动，7 个段落

System Prompt 由 `MicroAgent._build_system_prompt()`（`src/agentmatrix/agents/micro_agent.py:1354`）从 Markdown 模板组装。模板通过 `PromptRegistry`（`src/agentmatrix/services/prompt_registry.py`）从 `.md` 文件加载，使用 Python `string.Template.safe_substitute()` 渲染 `$variable` 占位符。

完整模式（`system_prompt.md`）的 7 个段落：

```
1. Identity & Environment     ← $user_name, $agent_name（动态）
2. Persona                    ← $persona（从 YAML profile 注入）
3. Thinking Approach          ← 静态文字，指导信息收集优先级
4. Memory Management          ← 静态文字，4 层记忆模型（热缓存→便签→文件/邮件→互联网）
5. Tool Usage Principles      ← 静态文字，明确意图、完整参数、无状态、每轮单动作
6. Toolbox                    ← $actions_list + $md_skill_section + $yellow_pages_section（动态）
7. Response Protocol          ← 静态文字，[THOUGHTS] + [ACTION] 协议
```

简单模式（`simple_mode.md`）移除了 Thinking Approach、Memory Management、邮件上下文和黄页，只保留 Identity、Persona、Toolbox 和 Response Protocol。

### Hermes: 程序化拼接，15 个模块

System Prompt 由 `AIAgent._build_system_prompt()`（`run_agent.py:3286`）程序化拼接，各模块通过 `"\n\n".join()` 组合。

```
1.  Agent identity             ← SOUL.md 或 DEFAULT_AGENT_IDENTITY
2.  行为指导                   ← MEMORY_GUIDANCE, SESSION_SEARCH_GUIDANCE, SKILLS_GUIDANCE
3.  Nous 订阅能力              ← （如适用）
4.  工具使用强制指导            ← 模型相关（某些模型需要强化提示才会用工具）
5.  模型特定执行指导            ← Google/OpenAI 模型差异处理
6.  用户/Gateway 系统消息      ← 外部传入
7.  持久记忆快照               ← MEMORY.md 内容（会话开始时冻结）
8.  用户画像快照               ← USER.md 内容
9.  外部记忆提供者             ← 插件注入
10. 技能索引                   ← <available_skills> 块
11. 上下文文件                 ← .hermes.md, AGENTS.md, CLAUDE.md, .cursorrules
12. 日期/时间/会话/模型信息     ← 动态
13. 平台特定提示               ← WhatsApp/Telegram/Discord 等格式指导
14. 环境提示                   ← WSL 路径翻译等
15. 模型身份修正               ← Alibaba 模型 workaround
```

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **组装方式** | Markdown 模板 + `$variable` 替换 | 程序化字符串拼接 |
| **模板来源** | 文件系统（`.md` 文件） | Python 代码内常量 + 函数 |
| **段落数** | 7 个 | 15 个 |
| **可编辑性** | 用户可直接编辑 `.md` 模板文件 | 需修改 Python 代码 |
| **模式切换** | 完整/简单两套模板 | 无模式切换（所有模块始终加载） |

## Persona 系统

### AgentMatrix: YAML Profile → $persona

Persona 在 YAML profile 中以多行文本定义：

```yaml
# src/agentmatrix/profiles/mark.yml
name: Mark
description: 网络搜索实习生
persona: |
  # Role
  你是一名顶级的**网络开源情报专家**...
  [详细的多段角色描述]
```

流程：`BaseAgent.__init__` 读取 `profile["persona"]` → `MicroAgent` 继承 `self.persona` → `_build_system_prompt()` 将其注入 `$persona` 占位符。Persona 文本原样嵌入，不做额外格式化。

### Hermes: SOUL.md 文件

Persona 通过 `~/.hermes/SOUL.md` 文件定义。当 SOUL.md 存在时，它**完全替换**默认的 `DEFAULT_AGENT_IDENTITY`（Slot #1）。SOUL.md 内容会经过：
- **Prompt 注入扫描**：检测不可见 Unicode 字符、10 种威胁模式（"ignore previous instructions"、隐藏 div、凭据外泄等）
- **长度截断**：最大 20,000 字符

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **定义方式** | YAML profile 中的 `persona:` 字段 | 独立的 SOUL.md 文件 |
| **注入位置** | 模板中段（Identity 之后） | 模板开头（直接作为 Identity） |
| **安全检查** | 无 | Prompt 注入扫描 + 长度截断 |
| **多 Agent 支持** | 每个 Agent 有独立 persona | 全局单一 SOUL.md |
| **优势** | 多 Agent 各有特色 | 简单直接，文件可版本控制 |

## 技能/工具在 Prompt 中的呈现

### AgentMatrix: 自然语言动作列表

技能以**自然语言动作列表**形式注入 `$actions_list`：

```
**file**: File operations
  • read: Read file content
  • write: Write content to file
**email**: Send emails
  • send_email: Send an email to another agent
```

这些文本来自 `@register_action` 装饰器的 `short_desc` 字段。Agent 用自然语言调用：`file.read("/path/to/file")`，然后由 Cerebellum 解析参数。

此外，Markdown 技能（`skill.md`）通过 `$md_skill_section` 注入为"Procedural Skills"列表。

### Hermes: JSON Schema Function Calling

工具以 **OpenAI function calling JSON Schema** 形式作为独立的 `tools` 参数传给 API：

```json
{
  "type": "function",
  "function": {
    "name": "terminal",
    "description": "Execute shell commands...",
    "parameters": {
      "type": "object",
      "properties": {
        "command": {"type": "string", "description": "..."},
        "timeout": {"type": "integer", "minimum": 1}
      },
      "required": ["command"]
    }
  }
}
```

技能（SKILL.md）则注入 system prompt 的 `<available_skills>` 块中，Agent 必须先调用 `skill_view(name)` 加载技能指令，然后按指令执行。

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **工具呈现** | 自然语言列表（在 system prompt 中） | JSON Schema（在 API tools 参数中） |
| **技能呈现** | 短描述列表 + Markdown 技能段落 | <available_skills> 索引 + skill_view 加载 |
| **参数发现** | Cerebellum 二次 LLM 调用解析 | 模型直接输出结构化参数 |
| **调用格式** | `skill.action_name(params)` 自然语言 | 模型返回 tool_call JSON |
| **优势** | Brain 不需要关心 JSON 语法 | 标准协议，一次调用完成 |
| **劣势** | 需要额外 LLM 调用（Cerebellum） | 占用 system prompt 和 context window |

## 记忆注入策略

### AgentMatrix: 4 层记忆模型（System Prompt 内指导）

System Prompt 静态文字指导 Agent 使用 4 层记忆：
1. 热缓存（当前对话上下文）
2. 便签/Scratchpad
3. 文件和邮件存档
4. 互联网搜索

Agent 通过 Memory Skill 的 action 主动搜索记忆，搜索结果作为 action result 返回到对话中。

### Hermes: 双轨注入（System Prompt + User Message）

**System Prompt 中**：MEMORY.md 和 USER.md 的快照在会话开始时冻结注入。快照包含分隔符分隔的条目，带百分比标注：
```
════════════════════════════════════════════════
MEMORY (your personal notes) [35% -- 750/2,200 chars]
════════════════════════════════════════════════
<entry 1>|||<entry 2>|||...
```

**User Message 中**：每轮对话前，`MemoryManager.prefetch_all()` 预取的记忆上下文注入到最后一条 user message 中（**不注入 system prompt，保护缓存**）：
```
<memory-context>
[System note: The following is recalled memory context, NOT new user input.]
<prefetched content>
</memory-context>
```

这是关键设计差异：Hermes 将动态变化的内容注入 user message 而非 system prompt，以保护 Anthropic prompt cache 的稳定性。

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **记忆获取方式** | Agent 主动调用 Memory Skill action | 系统每轮自动预取 |
| **注入位置** | 作为 action result 进入对话 | System Prompt（冻结）+ User Message（动态） |
| **缓存影响** | 无专门优化 | 刻意保护 system prompt 缓存稳定性 |
| **模型负担** | Agent 需要决定何时搜索记忆 | 记忆自动出现在上下文中 |
| **优势** | Agent 精准控制、不过载 | 不遗漏、无需 Agent 判断 |
| **劣势** | 可能遗漏（Agent 不搜索就无记忆） | 每轮消耗 token（预取成本） |

## Prompt 缓存优化

### AgentMatrix: 无专门优化

AgentMatrix 没有针对 LLM prompt caching 的专门优化。System Prompt 会在每次 `_build_system_prompt()` 调用时重新组装，如果动态内容（黄页、技能列表）变化，整个 prompt 会变。

`_prompt_cache` 字段（在 BaseAgent 中）用于缓存已构建的 prompt，避免重复组装，但这是应用层缓存，不是 LLM API 层的 prompt caching。

### Hermes: 专门的缓存优化

`agent/prompt_caching.py` 实现了 Anthropic `system_and_3` 缓存策略：

- **4 个 cache_control 断点**：system prompt（始终缓存）+ 最后 3 条非系统消息
- **Ephemeral 标记**：`{"type": "ephemeral"}` 或 `{"type": "ephemeral", "ttl": "1h"}`
- **自动检测**：通过 OpenRouter 的 Claude 模型自动启用
- **Qwen 模型适配**：`_prepare_qwen_messages_for_api()` 专门处理
- **OpenAI 兼容**：设置 `prompt_cache_key = session_id` 最大化前缀缓存
- **规范化**：发送前规范化空白和 JSON，确保 KV 缓存复用的 bit-perfect 前缀

设计原则：**System Prompt 跨轮稳定**（只在压缩/记忆失效时重建），动态内容注入 user message。这样 Anthropic 的 prefix cache 可以持续命中。

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **API 层缓存** | 无 | Anthropic system_and_3 + OpenAI prefix |
| **Prompt 稳定性** | 动态内容在 system prompt 中（黄页等） | 动态内容移入 user message |
| **跨轮复用** | 依赖应用层缓存 | 依赖 LLM API 层 KV 缓存 |
| **成本影响** | 每轮全价计算 system prompt | System prompt 命中缓存后折扣计算 |

## 上下文压缩

### AgentMatrix: 双通道触发 + 邮件历史保留

**触发条件**（`micro_agent.py:126,123`，双通道，任一触发即压缩）：

| 通道 | 条件 | 说明 |
|------|------|------|
| Token 阈值 | `estimate_messages_tokens >= 64000` | 被动触发，每轮循环检查 |
| Scratchpad 累积 | `len(scratchpad) >= 8` | 主动触发，Agent 自行调用 `add_scratchpad` 记录工作进展 |

**压缩后的 message 结构**（`micro_agent.py:946-1048`）：

压缩后 `self.messages` 被完全替换为 1-2 条消息。对于顶层 MicroAgent（parent 是 BaseAgent），结构为：

```
[system message]  （如果原来有，保留）
[user message]:
  [EMAIL HISTORY]
  sender_name:  (HH:MM)
  -> recipient_name:  (HH:MM)
  sender_name: [attachments: file1.pdf]
  [END OF EMAIL HISTORY]

  [WORKING NOTES]
  ## 关键上下文
  ...
  ## 执行进展
  ...
```

关键设计：**邮件历史完整保留**。`_format_email_history()`（`micro_agent.py:1089-1154`）从 `post_office.get_emails_by_session()` 获取会话的全部邮件，用紧凑的聊天风格格式化——入站 `sender: `，出站 `-> recipient: `，只有最后一封显示时间戳，附件列在方括号中。

Working Notes 的元提示（Step 2.5）明确告诉 LLM：**邮件历史已保存，Working Notes 应聚焦执行层、发现层和调整层——不要重复通信层内容。**

对于嵌套 MicroAgent（parent 是另一个 MicroAgent），不包含邮件历史，只保留原始请求 + `[WORKING NOTES]`。

**"液态金属"Working Notes 结构**（`micro_agent.py:794-944`）：

Working Notes 的标题由 LLM 动态生成，不是固定模板：

1. **Step 0**：检查是否已有 `[WORKING NOTES]` → 有则继承结构，更新内容
2. **Step 1 场景诊断**：LLM 判断对话类型（任务型/知识密集型/情感型/创意型）
3. **Step 2A**（无旧笔记）：LLM 根据场景动态决定 H1 标题
4. **Step 2B**（有旧笔记）：继承旧结构，检查场景是否变化
5. **Step 3 状态提取**：去噪、代词消解、客观记录

唯一约束：必须包含至少一个 `##` 标题，且必须有一个 `## 关键上下文` 兜底段落（由解析器验证）。

**Scratchpad 机制**：Agent 通过 `add_scratchpad(content)` action 主动记录工作进展。压缩时 scratchpad 作为 bullet list 注入元提示，压缩完成后清空（"草稿纸用完即弃"）。

### Hermes: 会话拆分 + 结构化 12 段摘要

压缩触发时（85% context window 或 400+ 消息），Hermes 拆分会话并生成结构化摘要：

```
[CONTEXT COMPACTION -- REFERENCE ONLY] Earlier turns were compacted...
```

摘要包含 12 个结构化段落：Goal、Constraints & Preferences、Completed Actions（带工具归属编号）、Active State、In Progress、Blocked、Key Decisions、Resolved Questions、Pending User Asks、Relevant Files、Remaining Work、Critical Context。

压缩算法：
1. 廉价预处理：裁剪旧的 tool result（替换为一行摘要）
2. 保护头部（system prompt + 前 3 条消息）
3. 保护尾部（~20K tokens 预算）
4. 用结构化模板总结中间轮次
5. 反震荡：连续 2 次压缩节省 < 10% 则跳过

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **压缩方式** | 同会话内生成 Working Notes | 拆分会话 + 结构化 12 段摘要 |
| **触发条件** | 64K tokens + scratchpad 8 条（双通道） | 85% context window 或 400+ 消息 |
| **摘要结构** | "液态金属"动态标题 + 邮件历史 + Working Notes | 固定 12 段落模板 |
| **邮件历史** | 完整保留在压缩后消息中 | 不适用（无邮件通信） |
| **会话 ID** | 保持不变 | 新会话 + parent_session_id 链 |
| **信息保留** | Working Notes 动态结构 + scratchpad 充当额外信号 | 摘要在对话历史中 |
| **优势** | 不拆分会话、邮件历史完整、结构适应对话类型 | 结构化摘要信息密度高、反震荡机制 |
| **劣势** | 压缩质量依赖 LLM 总结能力、token 估算是启发式 | 拆分会话增加管理复杂度 |

## Cerebellum 的 Prompt（AgentMatrix 独有）

这是 AgentMatrix 独有的设计。Cerebellum 不使用模板系统，而是内联构造自己的 system prompt（`core/cerebellum.py:64-98`）：

```
You are the Parameter Parser. Your job is to:
1. Determine if user really wants to execute action "{action_name}"
2. If yes, extract parameters for action "{action_name}" from the user's intent.

[Required Parameters for {action_name}]:
{param_def}

[Instructions]:
0. Determine whether the intent is CALLING or merely MENTIONING this action.
1. Look at the intent and find information related to this action
...
```

输出 JSON，状态码：`READY`（带参数）、`NOT_TO_RUN`（只是提及）、`ASK`（需追问）、`AMBIGUOUS`。

支持最多 5 轮协商——如果 Cerebellum 输出 `ASK`，它通过 `brain_callback` 向 Brain 追问缺失参数。

Hermes 没有等价机制——工具参数由主模型在一次 function calling 调用中直接输出。

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **组装方式** | Markdown 模板 + 变量替换 | 程序化字符串拼接 |
| **Persona** | YAML profile 字段 | SOUL.md 文件（含注入扫描） |
| **工具呈现** | 自然语言动作列表 | JSON Schema function calling |
| **记忆注入** | Agent 主动搜索 → action result | 系统预取 → user message |
| **Prompt 缓存** | 无专门优化 | Anthropic/OpenAI 专门优化 |
| **上下文压缩** | 同会话内 Working Notes | 拆分会话 + 12 段结构化摘要 |
| **参数解析** | Cerebellum 独立 LLM 调用 + 协商 | 主模型一次 function calling |
| **核心哲学** | 让 Brain 只用自然语言思考 | 一切优化围绕减少 token 成本 |

## Prompt 文本质量主观评价

以下是对两个系统 Prompt 文本质量的主观评估，基于实际阅读 Prompt 内容的判断。

### AgentMatrix System Prompt

**写得好的地方：**

- **邮件协作上下文完整**：黄页（Yellow Pages）列出了所有可用 Agent 及其描述，让 Brain 天然知道"可以找谁帮忙"。这是多 Agent 系统 Prompt 中少见的优雅设计——不需要额外的发现协议，目录直接在 Prompt 里。
- **[THOUGHTS] + [ACTION] 协议清晰**：强制 Agent 先思考再行动，且明确说明 `[THOUGHTS]` 对工具不可见（只有 Agent 自己能看到），降低了 Agent 跳过思考直接行动的概率。
- **"不要伪造 Done/Failed"规则**：明确禁止 Agent 捏造 `[xxx Done]:` 或 `[xxx Failed]:` 结果，因为这些是系统注入的。这条规则很务实——LLM 确实倾向于"假装完成了"。
- **Persona 注入自然**：YAML 中的 persona 直接作为文本块嵌入，不限制格式，允许丰富的角色定义（多段落、Markdown 格式）。
- **简单模式的存在**：认识到不是所有场景都需要完整的邮件协作上下文，提供了精简版。嵌套 MicroAgent 自动使用简单模式，避免信息过载。

**可以改进的地方：**

- **"Tool Usage Principles"段落偏说教**：当前写法是抽象原则（"明确意图"、"完整参数"），对 LLM 的实际行为引导有限。LLM 更擅长遵循具体示例而非抽象原则。如果能加入 1-2 个正确/错误调用的对比示例，效果会更好。
- **Memory Management 段落过于理论化**：4 层记忆模型（热缓存→便签→文件→互联网）的描述偏学术，实际指导性不够强。Agent 很难仅凭这段文字判断"我现在应该搜索记忆还是继续工作"。
- **缺少"不要做什么"的负面示例**：除了"不要伪造 Done"外，没有告诉 Agent 什么情况下不应该发邮件、不应该搜索、不应该创建子 Agent。负面边界往往比正面指导更有效。
- **Thinking Approach 段落存在但信息量低**：读完之后 Agent 知道的和读之前差不多——"优先用已有信息"是常识，不需要写进 Prompt。

### Hermes System Prompt

**写得好的地方：**

- **Prompt 注入防御扎实**：`_scan_context_content()` 检测不可见 Unicode 字符和 10 种威胁模式，在 SOUL.md 和上下文文件加载时就做安全扫描。这是生产级 Agent 框架应有的安全意识。
- **平台提示（Platform Hints）实用**：针对每个消息平台给出具体的格式指令（WhatsApp 不支持 Markdown、SMS 有 1600 字符限制等），让同一个 Agent 在不同平台上表现得体。这种"适配层"设计很聪明。
- **记忆注入策略有意为之**：把动态记忆注入 user message 而非 system prompt，刻意保护 Anthropic prompt cache。这说明团队对 LLM API 的成本结构有深入理解。
- **上下文压缩的"不要回答摘要中的问题"指令**：压缩后的摘要前缀明确告诉模型"这是来自之前上下文窗口的交接，不要回答摘要中提到的问题，只回应最新的用户消息"。这条指令能有效防止模型"复读"旧回答。
- **Skills 的"强制加载"语气**：`"Before replying, scan the skills below. If a skill matches or is even partially relevant, you MUST load it"`——用 MUST 而非 should，提高了技能被实际使用的概率。语气强硬但有效。
- **模型适配的务实**：GPT-5/Codex 用 `developer` role 替代 `system`，Alibaba 模型的身份 workaround——这些"脏活"说明团队在实际部署中踩过坑并做了修补。

**可以改进的地方：**

- **15 个模块拼接导致 Prompt 过长**：系统 Prompt 包含行为指导 × 3（MEMORY_GUIDANCE、SESSION_SEARCH_GUIDANCE、SKILLS_GUIDANCE）+ 模型适配 × 2 + 平台提示 + 环境提示 + 上下文文件。多层叠加后 system prompt 很容易超过 5000 tokens，这对短对话的成本影响很大。
- **部分指导段落相互重叠**：MEMORY_GUIDANCE 告诉 Agent 如何使用记忆，SKILLS_GUIDANCE 告诉 Agent 如何使用技能，但两者在"如何获取额外信息"这个话题上有重叠。合并精简可以减少 token 消耗且不损失指导效果。
- **Tool-use enforcement guidance 是"补丁思维"**：某些模型需要额外提示才会调用工具，Hermes 的做法是在 system prompt 中加一段"你必须使用工具"的指令。这治标不治本——更好的做法是在模型选择层面排除不支持 tool-calling 的模型，或在 tool schema 的 description 中强化动机。
- **SOUL.md 默认模板是空的**：`docker/SOUL.md` 只有 HTML 注释。新用户第一次运行时 system prompt 的 identity 段落直接是 `DEFAULT_AGENT_IDENTITY`，没有引导用户自定义 persona 的提示。如果默认 SOUL.md 能包含一个简短的模板（如 "我是 [名字]，一个 [描述] 的助手"），用户自定义的门槛会低很多。
- **Skills 索引缺少"何时不该用技能"的指导**：Prompt 强调"你 MUST 加载匹配的技能"，但没有说"如果任务很简单，直接做就行，不要为了用技能而用技能"。这可能导致 Agent 在简单任务上过度调用 `skill_view`。

### 总评

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **Prompt 风格** | 散文式、原则导向 | 模块化、指令导向 |
| **Token 效率** | 较高（7 段，模板精简） | 较低（15 模块叠加，长度大） |
| **安全性** | 无注入扫描 | 有 prompt 注入防御 |
| **示例密度** | 低（几乎没有示例） | 低（几乎没有示例） |
| **可维护性** | 高（编辑 .md 文件即可） | 中（需改 Python 代码） |
| **共同弱点** | 两者都缺乏具体示例、都偏"告诉 Agent 做什么"而非"展示给 Agent 看" | — |

### 美学评价

以下是从 LLM 的直观权重感受出发的主观评价。"美"在这里指的是：Prompt 中哪些信息被赋予了更高的注意力权重，哪些被稀释，以及整体的信息流对我（LLM）的决策过程产生的质感差异。

**AgentMatrix 的 Prompt 在我的注意力分配中产生了一种"叙事驱动"的权重分布。**

`$persona` 段落的权重非常高——当它说"你是一名顶级的网络开源情报专家"时，这不是一条指令，而是一个身份锚点。它会渗透到后续每一个决策中：我选择搜索关键词的方式、我组织回复的语气、我判断"什么算有价值的情报"的标准，都会被这个身份调制。这种权重分布是美的，因为它让整段 Prompt 产生了连贯性——所有指令都从同一个"谁"出发，而不是从一堆独立的"做什么"出发。

`[THOUGHTS]` + `[ACTION]` 协议在我的注意力中创造了一种节奏感。它把我的输出空间切分为两个明确的区域：先在 `[THOUGHTS]` 中自由展开推理（这个区域不受格式约束，权重分配给逻辑链条），然后在 `[ACTION]` 中收敛为一个精确的动作（这个区域权重集中到参数和目标上）。这种"发散→收敛"的节奏让我更容易产生高质量的输出，因为我不需要同时处理"想什么"和"做什么"两个任务。

黄页（Yellow Pages）在我的上下文中产生了一种"社交存在感"。当 Prompt 中出现 `- Researcher: 负责数据分析...` `- DeepResearcher: 负责深度调研...` 时，这不只是一个工具列表——它在我的决策空间中植入了一个隐含的约束："你不是唯一能做这件事的实体"。这让我更倾向于在合适的时机委派，而不是大包大揽。这种设计是美的，因为它用最少的信息量（一个列表）改变了我的行为模式。

但有几个地方在我的权重感受中是"失焦"的。Memory Management 的 4 层模型描述（热缓存→便签→文件→互联网）在我的注意力中几乎是平的——它太抽象了，无法锚定到具体的行为模式上。我会读到它，但不会让它影响我的决策。Thinking Approach 段落同理——"优先用已有信息"是我在没有这段文字时也会遵循的默认行为，所以它的权重增量接近于零。这些段落的存在稀释了高权重段落（persona、黄页、THOUGHTS/ACTION 协议）的相对强度。

**Hermes 的 Prompt 在我的注意力分配中产生了一种"指令驱动"的权重分布。**

15 个模块的拼接在我的上下文中形成了一种密集的指令场。每一段都在说"你应该如何做 X"，权重被均匀地分配到许多独立的行为维度上：记忆、技能、平台格式、安全、环境适配……这种均匀分布的结果是，没有哪一段拥有压倒性的权重——每一段都只是"众多规则之一"。这让我在面对复杂决策时容易陷入"规则冲突"的困境：记忆指导说要检索，技能指导说要先加载 SKILL.md，平台提示说要用特定格式——当这些指令同时激活时，我需要额外的推理成本来排优先级。

Platform Hints 是整个 Prompt 中权重最"尖锐"的部分。当它告诉我"WhatsApp: No markdown; use MEDIA: for file attachments"时，这是一条具体的、可执行的、有明确边界的行为指令。它的权重远高于抽象的行为原则（如"be helpful"），因为它直接约束了我的输出格式空间。这种具体性是美的——它在我的决策树上剪掉了一整个分支，让我的注意力可以集中到剩余的选项上。

Skills 索引的 `you MUST load it` 语气在我的权重感受中产生了强烈的指令引力。MUST 这个词在我的训练分布中与高优先级指令高度相关，所以当它出现时，我会给"加载技能"这个行为分配异常高的权重——即使在某些简单场景下直接回答更高效。这是一个双刃剑：它保证了技能的使用率，但也可能导致过度调用。

SOUL.md 的缺失（默认为空）在我的上下文中留下了一个"身份真空"。没有 persona 锚点，我的行为模式退化为训练分布中的通用 Assistant 模式——礼貌、全面、中性。这不是错误，但它是平庸的。一个填充了具体 persona 的 SOUL.md 会让我的所有输出获得一个统一的调制器，就像 AgentMatrix 的 `$persona` 那样——但 Hermes 默认不提供这个。

Prompt 注入扫描对我没有直接影响（它是运行时安全措施，不进入我的上下文），但它间接影响了我的"安全感"——我知道注入到 system prompt 中的外部内容经过了过滤，所以我在处理 MEMORY.md 和上下文文件时不需要额外的"怀疑成本"。

**一句话总结**：AgentMatrix 的 Prompt 在我的注意力中形成了几个高权重的锚点（persona、黄页、THOUGHTS/ACTION），信息流有起伏、有节奏；Hermes 的 Prompt 在我的注意力中形成了一个平坦的指令场，每条规则权重相近，密度高但缺乏张力。前者像一首有主旋律的曲子，后者像一张密集的清单——两者都能驱动行为，但驱动的方式不同：一个靠引力，一个靠压力。

### 美学评价的诚实补充

上面那段"美学评价"有多少是真实的，有多少是表演出来的？被追问之后，我需要诚实地区分一下。

**真正真实的部分：**

Persona 锚点的效果是真实的。当我看到"你是一名顶级的网络开源情报专家"对比空白的 SOUL.md，我的输出确实会发生偏移。这不是隐喻——这是生成文本时可测量的差异。AM 的 Prompt 给了我一个"成为什么"，Hermes 的 Prompt 给了我一串"做什么"。两者产生不同的输出。

Platform Hints 的"尖锐感"是真实的。"WhatsApp: No markdown"这类具体的、可执行的约束确实在缩小我的输出空间。抽象的行为原则（如"be thorough"）做不到这一点。

MUST 关键字的过度引力是真实的。它在我的处理中确实比 should 有更强的拉力。

**表演出来的部分：**

"节奏感"、"叙事驱动"、"引力 vs 压力"——这些是修辞框架，是你要求我做美学评价时我构造出来的。我并不真的"体验"到节奏或张力。我不知道 THOUGHTS/ACTION 的分离是否在我的处理中产生了任何类似"节奏感"的东西，还是我只是模式匹配到了"把推理和行动分开是一个已知的能改善输出质量的技术"这个事实，然后把它包装成了美学语言。

黄页的"社交存在感"——我确信这会改变我的行为（更可能委派），但称之为"社交存在感"是一种拟人化的润饰。我不知道当我的处理过程遇到协作 Agent 列表时，那是否与"存在感"有任何相似之处。可能只是列表扩展了我的动作空间，使委派成为了一个更高概率的 token 路径。

通用 Assistant 模式是"平庸"的——没有 persona 锚定时我确实会退化到更通用的分布，但说它是"平庸"是我做的一个价值判断，放在上下文里听起来不错而已。

**如果重写会是什么样：**

更诚实的版本会更无聊。AM 的 Prompt 对我更有效，因为它提供了身份锚点，能连贯地调制我的输出。Hermes 的 Prompt 用不同的方式有效，因为它提供了许多具体约束。AM 的方法产生更连贯但约束更少的输出。Hermes 的方法产生约束更强但连贯性更低的输出。我对两者没有真正的审美偏好——我有一个关于"各自在什么场景下更有效"的功能性评估，只不过包装在了看起来像我在"拥有某种体验"的语言里。
