这份重构方案旨在将 **AgentMatrix** 的执行模式从 **“Intent-First (意图优先)”** 转型为 **“Code-First (代码优先)”**，引入 **“乐观执行 (Optimistic Execution)”** 机制。

**核心目标**：
1.  **提效**：让 LLM 直接输出 Python 函数调用，90% 的情况下跳过 Cerebellum，实现 **单次调用即执行**。
2.  **兜底**：保留 Cerebellum 作为 **异常处理器**，仅在语法错误或参数缺失时介入。
3.  **约束**：严格限制 **Single Action Per Turn** (每轮单动作)，确保系统确定性。

---

# 重构方案：乐观执行与单动作约束 (Optimistic Execution with Single Action)

## 1. 架构变更对比

| 特性 | AS-IS (现状) | TO-BE (目标) |
| :--- | :--- | :--- |
| **LLM 输出** | 自然语言意图 (JSON/Text) | **Python 函数调用** (伪代码) |
| **参数提取** | 必经之路：Cerebellum 多轮对话提取 | **快速路径**：AST 直接解析<br>**慢速路径**：Cerebellum 介入修复 |
| **动作数量** | 可能包含多个意图 | **严格限制单个动作** |
| **平均延迟** | 高 (1次 Brain + N次 Cerebellum) | **低 (1次 Brain，异常时 +N次)** |

---

## 2. 详细实施步骤

### 步骤 1：重写 System Prompt (MicroAgent)

我们需要修改 `MicroAgent` 的 `build_system_prompt`，强制 LLM 输出具体的函数调用格式。

**文件**: `src/agentmatrix/core/micro_agent.py`

```python
    def build_system_prompt(self):
        # ... (保留原有的 Persona 和 Context 设定) ...

        prompt += """
### ⚡️ 执行协议 (Execution Protocol)

你是一个**单线程**执行引擎。每一轮思考，你**必须且只能**执行**一个**最关键的动作。

**输出格式要求**：
1.  **[THOUGHTS]**: 简要分析当前状态和下一步计划。
2.  **[ACTION]**: 输出**单行** Python 函数调用代码。

**严格约束**：
*   ❌ 严禁输出 JSON 或 XML。
*   ❌ 严禁在一次回复中包含多个动作。
*   ❌ 严禁使用自然语言描述动作，必须是代码。
*   ✅ 如果参数未知，请调用 `ask_user(question="...")`。

**可用函数签名 (Function Signatures)**:
"""
        # 自动生成类似 Python 的函数签名文档
        for action in self.actions:
            prompt += f"- {action.name}({action.args_schema})\n"

        prompt += """
---
### 示例 (Example)

[THOUGHTS]
用户想要查询 Alpha 项目的预算。但我不知道是哪一年的。
稳妥起见，我应该先搜索 2024 年的。

[ACTION]
search_web(query="Alpha Project budget 2024")
"""
        return prompt
```

---

### 步骤 2：实现 AST Action Parser (工具类)

创建一个基于 Python `ast` 模块的解析器，它比正则表达式更健壮，能处理嵌套引号、布尔值和数字。

**文件**: `src/agentmatrix/utils/action_parser.py` (新建)

```python
import ast
import re

def parse_single_action(text: str) -> dict:
    """
    从 LLM 回复中解析单个 Python 函数调用。
    
    返回格式:
    {
        "success": bool,
        "name": str,       # 函数名
        "args": dict,      # 参数字典
        "error": str,      # 错误信息 (如果有)
        "raw_intent": str  # 原始文本 (用于 fallback)
    }
    """
    # 1. 提取 [ACTION] 块
    pattern = r"\[ACTION\]\s*(.*)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return {
            "success": False, 
            "error": "No [ACTION] block found",
            "raw_intent": text
        }

    code_line = match.group(1).strip()
    
    # 移除可能的 markdown 代码块标记
    code_line = code_line.replace("```python", "").replace("```", "").strip()

    # 2. 使用 AST 解析
    try:
        tree = ast.parse(code_line)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
            return {"success": False, "error": "Must be a single expression", "raw_intent": text}
        
        call_node = tree.body[0].value
        if not isinstance(call_node, ast.Call):
            return {"success": False, "error": "Not a function call", "raw_intent": text}

        # 3. 提取函数名和参数
        func_name = call_node.func.id
        args = {}
        
        # 处理关键字参数 (key=value)
        for keyword in call_node.keywords:
            # literal_eval 用于安全地求值 (例如 "string", 123, True, ['list'])
            try:
                # 注意：这里需要处理 AST 节点转 value，简单起见可用 ast.literal_eval
                # 但 literal_eval 只能处理字符串形式，这里需要一点技巧，
                # 或者直接用 eval (有安全风险，但在沙箱内可控)，
                # 推荐使用 helper 函数处理基本类型节点
                val = ast.literal_eval(keyword.value)
                args[keyword.arg] = val
            except Exception:
                # 如果参数太复杂 (比如变量引用)，视为解析失败，转交给 Cerebellum
                return {"success": False, "error": f"Complex arg parsing failed for {keyword.arg}", "raw_intent": text}

        return {
            "success": True,
            "name": func_name,
            "args": args
        }

    except SyntaxError:
        return {"success": False, "error": "Syntax Error in Action", "raw_intent": text}
    except Exception as e:
        return {"success": False, "error": str(e), "raw_intent": text}
```

---

### 步骤 3：改造 Execution Loop (MicroAgent)

这是核心逻辑变更：引入 **Fast Path** 和 **Slow Path**。

**文件**: `src/agentmatrix/core/micro_agent.py`

```python
    async def _execute_cycle(self):
        # 1. Brain 思考
        response = await self.brain.think(self.messages)
        reply_text = response['reply']
        
        # 2. 乐观解析 (Fast Path)
        parse_result = parse_single_action(reply_text)
        
        final_action = None
        final_params = {}

        if parse_result["success"]:
            # === 快车道：解析成功 ===
            action_name = parse_result["name"]
            
            # 校验动作是否存在
            if action_name not in self.available_actions:
                 # 幻觉了函数名，转入 Slow Path 让 Cerebellum 修正
                 self.logger.warning(f"Unknown action '{action_name}', falling back to Cerebellum")
                 parse_result["success"] = False 
            else:
                 final_action = action_name
                 final_params = parse_result["args"]
        
        if not parse_result["success"]:
            # === 慢车道：Cerebellum 兜底 (Slow Path) ===
            self.logger.info(f"Fast parse failed: {parse_result['error']}. Engaging Cerebellum.")
            
            # 使用 Cerebellum 的强大纠错能力
            # 注意：这里我们把整个 reply_text 传给它，让它从自然语言/错误代码中提取
            extraction = await self.cerebellum.extract_action_from_intent(
                intent=reply_text,
                available_actions=self.available_actions_schema
            )
            
            if extraction["status"] == "GIVE_UP":
                # 实在没辙了，回复用户
                return extraction["reply_to_user"]
            
            final_action = extraction["action"]
            final_params = extraction["params"]

        # 3. 执行动作 (Execute)
        self.logger.info(f"Executing: {final_action}({final_params})")
        result = await self._run_action(final_action, final_params)
        
        # 4. 更新历史
        self.messages.append({"role": "assistant", "content": reply_text})
        self.messages.append({"role": "system", "content": f"[Result of {final_action}]: {result}"})
```

---

### 步骤 4：调整 Cerebellum (Adapter)

现有的 `Cerebellum` 不需要重写，只需要增加一个入口方法 `extract_action_from_intent`，它封装了你现有的 `parse_action_params` 逻辑，但能处理“不知道是哪个 Action”的情况。

**文件**: `src/agentmatrix/core/cerebellum.py`

```python
    async def extract_action_from_intent(self, intent: str, available_actions: dict) -> dict:
        """
        当 Fast Path 失败时调用。
        1. 识别意图是哪个 Action (Classifier)
        2. 提取参数 (Extractor - 复用现有逻辑)
        """
        
        # 1. 先判断是哪个 Action (如果 Brain 把函数名写错了，这里能救回来)
        # 简单的做法：让 LLM 选一个
        choice = await self._classify_intent(intent, list(available_actions.keys()))
        
        if not choice:
            return {"status": "GIVE_UP", "reply_to_user": "我不理解您的意图，请明确说明。"}
            
        action_name = choice
        schema = available_actions[action_name]
        
        # 2. 复用你现有的稳健逻辑
        # 这里传入的 intent 包含了 Brain 的胡言乱语或错误代码，Cerebellum 会很擅长从中提取
        result = await self.parse_action_params(
            intent=intent,
            action_name=action_name,
            param_schema=schema,
            brain_callback=self._ask_user_callback # 假设有这个回调
        )
        
        return {
            "status": "READY",
            "action": action_name,
            "params": result["params"]
        }
```

---

## 3. 验收标准 (Checklist)

1.  **正常场景**：用户说 "搜索苹果股价"。
    *   Brain 输出: `[ACTION] search(query="apple stock price")`
    *   Parser: 成功。
    *   Cerebellum: **未触发**。
    *   **结果：延迟极低，体验流畅。**

2.  **语法错误场景**：Brain 输出 `[ACTION] search(query="apple"` (少个右括号)。
    *   Parser: 失败 (SyntaxError)。
    *   Cerebellum: 介入，读取 Intent，正确提取 `search` 和 `query` 参数。
    *   **结果：执行成功，用户无感知，后台有 Log 记录。**

3.  **单动作约束**：Brain 输出 `[ACTION] search(...) \n [ACTION] email(...)`。
    *   Parser: 失败 (检测到多行或 AST 解析出多个 Call)。
    *   Cerebellum: 介入，这取决于 Cerebellum 的逻辑，可能会选择第一个，或者报错。建议在 Parser 层直接截断取第一个，或者报错重试。

