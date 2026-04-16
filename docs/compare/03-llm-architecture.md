# 03 — LLM 架构与 Brain 设计

## 双脑 vs 单脑

这是两个项目最根本的架构分歧之一。

### AgentMatrix: Brain + Cerebellum 双脑架构

AgentMatrix 将 LLM 调用分为两个角色：

**Brain（大模型）**：负责推理和决策。Agent 的 System Prompt 中 Brain 以自然语言思考，输出 `[THOUGHTS]` 和 `[ACTION]` 标签。Brain 不需要关心 JSON 格式或参数细节，只需表达意图。

**Cerebellum（小模型）**（`src/agentmatrix/core/cerebellum.py`）：负责参数解析和协商。Cerebellum 接收 Brain 的自然语言意图，解析出结构化参数：

```python
class Cerebellum(AutoLoggerMixin):
    async def parse_action_params(self, intent, action_name, param_schema,
                                   brain_callback, task_context="") -> dict:
        # 1. 判断是"调用"还是"提及"该 action
        # 2. 从自然语言意图中提取参数
        # 3. 如果参数缺失，通过 brain_callback 向 Brain 追问（最多 5 轮）
        # 4. 返回结构化参数
```

关键设计点：
- **调用 vs 提及判断**：Cerebellum 区分"要执行这个 action"和"只是提到这个 action 的名字"
- **多轮协商**：参数缺失时，Cerebellum 向 Brain 追问，最多 5 轮
- **成本优化**：Cerebellum 使用更小、更便宜的模型，将参数解析的开销从大模型转移

### Hermes Agent: 单 LLM 全权处理

Hermes 使用单个 LLM 同时处理推理和工具参数提取。通过 OpenAI-compatible function calling 接口，模型在一次调用中同时决定"做什么"和"参数是什么"：

```python
response = client.chat.completions.create(
    model=model, messages=messages, tools=tool_schemas
)
# 模型同时返回: 要调用的工具名 + 结构化参数
```

这种方式更简单，但所有推理和参数提取的成本都由同一个（通常是大）模型承担。

### 对比

| 维度 | AgentMatrix (双脑) | Hermes (单脑) |
|------|-------------------|---------------|
| **推理成本** | Brain 大模型 + Cerebellum 小模型，参数解析成本低 | 全部由主模型承担 |
| **延迟** | 双 LLM 调用增加延迟 | 单次调用，延迟更低 |
| **准确性** | Cerebellum 专门训练做参数解析 + 协商机制兜底 | 依赖模型的 function calling 能力 |
| **架构复杂度** | 高（两个 LLM 协作、协商机制） | 低（标准 tool-calling） |
| **适用场景** | Agent 频繁调用 action，参数解析量大 | 工具调用不频繁或参数简单 |

## LLM 提供商抽象

### AgentMatrix

`src/agentmatrix/backends/llm_client.py`（~58KB）实现统一的多提供商客户端：

- 支持 OpenAI、Anthropic、Google 等 API
- `think_with_retry` 模式确保结构化输出的可靠性
- Brain 和 Cerebellum 可以使用不同提供商/模型
- 每个 Agent 的 YAML 配置可指定不同模型

### Hermes Agent

Hermes 以 OpenAI-compatible API 为基础，通过 OpenRouter 支持 200+ 模型：

- 核心依赖 `openai` Python SDK
- 支持 Anthropic（通过 Anthropic SDK 直连）、OpenAI、Google Gemini、Hugging Face、本地服务器（Ollama、LM Studio、vLLM）等
- 提供 provider failover 机制（错误分类 + 自动切换）
- 模型元数据自动探测（context length、token limits）

## 多模态支持

### AgentMatrix: 独立 vision_brain

AgentMatrix 将视觉能力作为独立的 `vision_brain` 组件，与普通 Brain 分离。需要视觉推理的任务切换到 vision_brain 处理。

### Hermes Agent: Vision Tool

Hermes 将视觉作为工具之一（`tools/vision_tools.py`），在 agent loop 中像其他工具一样被调用。模型通过 tool call 决定何时需要视觉分析。

## Prompt 工程

### AgentMatrix: YAML 人格 + 模板系统

- **YAML Agent Profile**：每个 Agent 的 persona 定义在 YAML 文件中（`src/agentmatrix/profiles/*.yml`）
- **System Prompt 模板**：Jinja2 模板动态生成（`docs/core/07-*.md`）
- **PromptRegistry**：集中管理模板版本和渲染
- **两种模式**：简单模式（嵌套 MicroAgent）和完整模式（顶层 Agent）

### Hermes Agent: agentskills.io 标准

- 技能遵循 [agentskills.io](https://agentskills.io) 开放标准
- 每个技能是一个目录，包含 `SKILL.md`（指令）和可选参考文档
- System Prompt 通过 `agent/prompt_builder.py` 动态组装
- 支持 `SOUL.md` 人格模板（Docker 部署）

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **核心创新** | 双脑分离（推理 vs 参数解析） | 单脑 + 标准 function calling |
| **成本模型** | 混合成本（大+小模型） | 统一成本（单一模型） |
| **提供商数量** | OpenAI/Anthropic/Google | 200+（通过 OpenRouter） |
| **多模态** | 独立 vision_brain 组件 | Vision tool（工具之一） |
| **Prompt 标准** | 自有 YAML 模板系统 | agentskills.io 开放标准 |
| **优势** | 参数解析成本低、协商机制鲁棒 | 架构简单、模型选择广泛 |
| **劣势** | 双 LLM 延迟、架构复杂 | 大模型承担所有推理成本 |
