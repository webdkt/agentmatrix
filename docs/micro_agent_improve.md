要解决的问题：**LLM 的“输出”与程序的“返回值”之间的阻抗不匹配（Impedance Mismatch）。**

目前你的实现中，`finish_task` 只是一个普通的 Action，它返回一个字符串给 LLM（作为 Observation），然后 MicroAgent 依靠检测 `action_name == exit_condition` 来强行结束循环，并去 parse `think` 或者 `finish_task` 的参数里的字符串。

这确实是**权宜之计**，存在以下问题：
1.  **类型丢失**：只能返回字符串。如果 Micro Agent 做了一个复杂的计算，想返回一个 `List[Dict]` 或者一个 `Image` 对象，必须序列化成字符串再反序列化，非常低效且容易出错。
2.  **控制流混乱**：`MicroAgent` 的主循环既要管“调用 Action”，又要管“检测是否结束”，逻辑耦合。
3.  **结果归属不清**：如你所说，如果一个 Micro Agent 调用了另一个 Micro Agent，由于都只是返回字符串，上层很难拿到下层真正的结构化产出。

我们需要引入**“控制信号（Control Signals）”**的设计模式，利用 Python 的异常机制或者特殊的返回值对象，来优雅地实现“函数式返回”。

以下是我的改进建议，旨在实现**强类型的、像函数调用一样的 Micro Agent**。

### 核心设计理念：Action 即控制流

我们规定：**任何 Action 都可以抛出一个“结束信号”，携带最终的返回值。**
`finish_task` 不再是一个普通的 Action，而是一个**“终结符（Terminator）”**。

#### 1. 定义一个用于携带结果的信号

不要用 return，用 Exception。这是一种在解释器模式（Agent 其实就是一个自然语言解释器）中非常常见的设计，用于跳出多层循环。

```python
# core/signals.py

class AgentReturnSignal(Exception):
    """
    用于中断 Agent 思考循环并返回结果的信号。
    携带的数据可以是任意类型 (Any)，不仅仅是字符串。
    """
    def __init__(self, value: Any):
        self.value = value
```

#### 2. 改造 `finish_task` Action

`finish_task` 的实现不再是返回字符串给 LLM，而是直接**抛出信号**。

```python
# micro_agent.py (或者单独的 actions 模块)

def create_finish_action(output_type: type = str):
    """
    工厂函数：创建一个带有特定类型提示的 finish_task
    """
    
    # 动态生成参数描述，提示 LLM 需要返回什么类型
    # 这里只是简化演示，实际可以使用 Pydantic model dump json schema
    param_desc = "The final result." if output_type is str else f"The final result object of type {output_type.__name__}"

    async def finish_task(result: Any):
        """
        [TERMINAL ACTION] 
        Call this when the task is completed. The 'result' parameter will be returned to the caller.
        """
        # 直接抛出信号，携带结果
        raise AgentReturnSignal(value=result)
    
    # 附加元数据
    finish_task._is_action = True
    finish_task._action_desc = "Finish the task and return the result."
    finish_task._action_param_infos = {"result": param_desc}
    
    return finish_task
```

#### 3. 改造 `MicroAgent.execute`：捕获信号

主循环变得异常干净：它只管执行，直到有人喊“停”。

```python
# micro_agent.py

class MicroAgent(AutoLoggerMixin):
    # ... init ...

    async def execute(self, ... exit_condition: str = "finish_task") -> Any: # 注意返回值是 Any
        # ... 初始化 context ...
        
        # 确保 finish_task 在可用列表中，并且它是一个会抛出 AgentReturnSignal 的函数
        # 这里你可以动态注入 finish_task，或者要求 action_registry 里必须有
        
        try:
            # === 主循环 ===
            for self.step_count in range(1, self.max_steps + 1):
                # 1. Think
                thought = await self._think()
                
                # 2. Detect
                action_name = self._detect_action(thought)
                
                if action_name:
                    # 3. Execute Action
                    # 关键点：如果执行的是 finish_task，这里会直接抛出 AgentReturnSignal
                    # 从而跳出整个 try block，直接进入 except
                    result = await self._execute_action(action_name, thought)
                    
                    # 如果是普通 Action，记录结果并继续循环
                    self._add_message("assistant", thought)
                    self._add_message("user", f"Action '{action_name}' executed. Result: {result}")
                else:
                    self._add_message("assistant", thought)
                    self._add_message("user", "Please use an available action.")
            
            # 如果循环跑完了还没抛出信号
            return "Task exceeded max steps without result."

        except AgentReturnSignal as e:
            # === 捕获返回值 ===
            # 这就是我们要的那个“函数返回值”，它是强类型的
            self.logger.info(f"Micro Agent {self.name} finished with return value: {e.value}")
            return e.value
            
        except Exception as e:
            self.logger.exception("Unexpected error")
            return f"Error: {e}"
```

### 这种设计如何解决你的痛点？

#### 场景一：嵌套调用与结果传递

假设你有一个 `SummarizerAgent` (上层) 调用 `WebReaderAgent` (下层)。

**下层 (WebReaderAgent):**
它的 `action_registry` 里有一个 `read_page` (普通Action) 和 `finish_task` (终结Action)。
当它读完网页，想返回内容时：
LLM 决定调用: `finish_task(result={"url": "...", "content": "..."})`。
`finish_task` 实现抛出 `AgentReturnSignal(dict)`。
`WebReaderAgent.execute` 捕获信号，**直接返回这个 dict**。

**上层 (SummarizerAgent):**
它的 `action_registry` 里有一个 Action 叫 `browse_web`。
`browse_web` 的 Python 实现如下：

```python
async def browse_web(url: str):
    # 实例化一个临时的下层 Agent
    reader = MicroAgent(brain, cerebellum, actions, name="Reader")
    
    # 执行它！
    # 因为 MicroAgent.execute 现在返回的是 Any (在这个case里是 dict)
    # 所以 browse_web 直接拿到了结构化数据！
    page_data = await reader.execute(task=f"Read {url}...", ...)
    
    # 这里可以做处理，或者直接返回给上层 LLM 放入 Observation
    return f"Read success. Title: {page_data['title']}, Length: {len(page_data['content'])}"
```

#### 场景二：返回非文本对象

假设 `DataAnalystAgent` 生成了一个 `matplotlib` 的 `Figure` 对象。
它调用 `finish_task(result=my_figure_object)`（这里假设是 Python 代码执行环境，或者它引用了一个变量名）。
信号携带 `Figure` 对象跳出。
`MicroAgent.execute` 返回 `Figure` 对象。
调用者（可能是 UI 渲染层）直接拿到对象进行展示，而不需要从字符串里去 parse。

### 总结：通用的设计模式

你需要的不仅仅是一个 Micro Agent，而是一个 **"LLM Runtime Stack"**。

1.  **Call Stack（调用栈）**：就像 Python 函数调用一样，Micro Agent A 调用 Action B，Action B 内部启动 Micro Agent C。
2.  **Return Value（返回值）**：通过 `AgentReturnSignal` 实现，它打断当前的 Event Loop，将数据向上一层传递。
3.  **Type Safety（类型安全）**：虽然 LLM 内部是自然语言（弱类型），但在 Action 的边界（输入参数解析和输出信号）通过 Python 代码强制转换和封装，保证了 Agent 之间交互的强类型。

**修改建议：**

1.  去掉 `execute` 方法中依靠 `exit_condition` 字符串匹配退出的逻辑。
2.  创建一个 `finish_task` (或叫 `return_result`) 的标准 Action 实现，它的唯一作用就是 `raise AgentReturnSignal(args)`。
3.  在 `execute` 的最外层 `try...except AgentReturnSignal` 来捕获结果。

这样，你的 Micro Agent 就真正变成了一个**"概率性的、自然语言驱动的、但返回确定性结果的 Python 异步函数"**。


有点启发。你发现没有，我们在设计如何使用**"概率性的、自然语言驱动的函数"**，你看前面的许多设计（包括小脑的negotiate），是为了让缝合自然语言到 function interface之间的gap（用小脑来填充json，获取需要的参数，但因为语言的不确定性和LLM的不确定性，这个过程可能有问题，需要多轮的沟通来容错）。但这个机制，解决了输入的问题，启动函数的问题。现在要解决的是硬币的另一面：获取这种不确定的函数的输出。我理解你的设计。但似乎没有能够完全缝合好这个gap，你觉得呢？都再想想


你这是一个非常敏锐且深刻的洞察。

你是对的。目前的架构在“输入端”做了很重的工作（Cerebellum, Negotiate Loop）来弥合 **自然语言 -> 确定性函数参数** 的 Gap。但在“输出端”，我们目前的设计（简单的 `finish_task(result_string)`）确实过于草率，没有对称地去弥合 **LLM的模糊输出 -> 确定性程序对象** 的 Gap。

**这种“不对称性”就是问题的根源。**

如果把 Micro Agent 看作一个函数 `f(x)`：
*   **输入端 (x)**：我们有 `Cerebellum` 作为“参数适配器”和“类型检查器”。
*   **输出端 (y)**：目前是一个黑洞。LLM 随意扔出来一个字符串，上层程序还得自己想办法去解析，或者干脆拿不到结构化数据。

要真正“缝合”这个 Gap，我们需要引入一个对称的概念：**输出端协商 (Output Negotiation)**。

### 核心设计：双端契约架构 (Dual-End Contract Architecture)

我们需要把 Micro Agent 升级为一个**“强类型函数”**。这意味着在调用它之前，我们不仅要定义它能做什么（Actions），还要定义它**必须返回什么结构的数据（Output Schema）**。

#### 1. 定义契约：Pydantic 作为桥梁

我们利用 `Pydantic` 模型来定义输出契约。这既是给 Python 代码看的（类型定义），也是给 LLM 看的（Schema 描述）。

```python
from pydantic import BaseModel, Field
from typing import List

# 定义我们期望 Micro Agent 返回的结构化数据
class ResearchResult(BaseModel):
    summary: str = Field(..., description="对研究主题的简要总结")
    key_facts: List[str] = Field(..., description="提取出的关键事实列表")
    confidence_score: float = Field(..., description="信息的可信度评分 0.0-1.0")
```

#### 2. 动态生成“终结工具” (The Projected Terminator)

这是最关键的一步。我们不再使用通用的 `finish_task(result: str)`。
相反，**我们根据 Output Schema 动态生成一个专门的 `submit_result` 工具**。

如果是上面的 `ResearchResult`，Micro Agent 看到的 `finish` 工具签名会自动变成：
`submit_result(summary: str, key_facts: List[str], confidence_score: float)`

这样，LLM 在想要结束任务时，**被迫**按照我们的结构填充数据。

#### 3. 输出端的“协商循环” (Output Negotiation Loop)

就像输入端 Cerebellum 发现参数缺失会反问 Brain 一样，输出端也需要一个监视器。
当 LLM 调用 `submit_result` 时，我们的 Python 代码（Runtime）会拦截这个调用：
1.  **验证**：用 Pydantic 校验 LLM 填入的参数。
2.  **通过**：如果校验通过，实例化对象，抛出 `AgentReturnSignal`（携带强类型对象）。
3.  **驳回**：如果校验失败（例如 `confidence_score` 填了字符串，或者 `key_facts` 为空），**不结束任务**，而是把错误信息作为 `Tool Output` 反馈给 LLM。
    *   *System Feedback*: "Error: 'confidence_score' must be a float. Please correct your submission."
    *   *LLM Reaction*: "Ah, sorry." -> Re-call `submit_result` with correct types.

---

### 代码实现：闭环的 Micro Agent

下面是修改后的设计，它真正实现了“输入-输出”的对称治理。

```python
# micro_agent_v2.py

from pydantic import BaseModel, ValidationError
from typing import Type, TypeVar, Any, Dict, List
import inspect

# 定义泛型，用于类型提示
T = TypeVar("T", bound=BaseModel)

class AgentReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value

class TypedMicroAgent(MicroAgent):
    
    async def execute_typed(
        self, 
        task: str, 
        output_schema: Type[T],  # <--- 核心变化：传入期望的输出类型
        available_actions: List[str],
        **kwargs
    ) -> T:  # <--- 核心变化：返回值是强类型的 T
        
        # 1. 动态生成“提交结果”的 Action
        submit_action = self._create_submit_action(output_schema)
        
        # 2. 将这个特殊的 Action 注入到 registry 中
        #    并强制将其作为唯一的退出机制
        action_name = "submit_result"
        self.action_registry[action_name] = submit_action
        if action_name not in available_actions:
            available_actions.append(action_name)
            
        # 3. 更新 Prompt，明确告知 LLM 必须使用这个工具来交付成果
        schema_json = output_schema.model_json_schema()
        # 这里你可以把 schema 描述放进 System Prompt
        
        try:
            # 4. 执行常规循环
            # 注意：exit_condition 不再是简单的字符串匹配，而是依靠 submit_action 抛出异常
            await super().execute(
                task=task, 
                available_actions=available_actions, 
                exit_condition=action_name,
                **kwargs
            )
            # 如果跑完步数还没抛出异常
            raise TimeoutError("Agent failed to submit result in time.")
            
        except AgentReturnSignal as e:
            # 5. 捕获强类型结果并返回
            return e.value

    def _create_submit_action(self, schema: Type[T]):
        """
        根据 Pydantic Model 动态生成 Action 函数
        """
        
        # 动态生成函数签名和文档，让 LLM 能理解
        # 这里利用了 Pydantic 的内省能力
        
        async def submit_result(**kwargs):
            try:
                # === 输出端协商的核心 ===
                # 尝试用 LLM 提供的参数实例化 Pydantic 对象
                result_object = schema(**kwargs)
                
                # 校验成功！抛出信号，携带这个对象跳出循环
                raise AgentReturnSignal(value=result_object)
                
            except ValidationError as e:
                # === 校验失败 ===
                # 不要崩溃，而是返回错误信息给 LLM，让它重试
                # 这就是 Output Negotiation
                error_msg = f"Submission Rejected. Validation Errors:\n{e.json()}"
                return error_msg

        # 伪装函数的元数据，让 BaseAgent/Cerebellum 能识别它
        submit_result._is_action = True
        submit_result._action_desc = f"Submit the final result. STRICTLY follow this schema: {schema.model_json_schema()}"
        # 这里需要把 Pydantic fields 转换成 param_infos
        submit_result._action_param_infos = {
            name: field.description or "No description" 
            for name, field in schema.model_fields.items()
        }
        
        return submit_result
```

### 这种设计的深层含义

1.  **Gap 的真正缝合**：
    *   **Action Call (Input)**: `Intention -> [Negotiation] -> Valid Arguments`
    *   **Result Return (Output)**: `Conclusion -> [Negotiation] -> Valid Object`
    *   现在的 Micro Agent 就是一个完全包裹在“类型安全膜”里的不确定性内核。

2.  **解决“中间状态”与“最终结果”的混淆**：
    *   你提到的“中间过程累积（如 Research）”发生在 Micro Agent 的内部状态（Memory/History）或者外部副作用（File System）中。
    *   `submit_result` 不负责承载所有中间数据，它负责承载**结论**。
    *   如果任务是“写一份总结”，`submit_result` 的参数就是 `summary` 字符串。
    *   如果任务是“收集数据”，`submit_result` 的参数可能是 `output_file_path` 或者一个包含关键数据的列表。

3.  **组合性 (Composability)**：
    *   现在上层代码可以这样写：
        ```python
        # 完全像调用普通函数一样，但是是自然语言驱动的
        result: ResearchResult = await researcher.execute_typed(
            task="分析 NVIDIA 财报",
            output_schema=ResearchResult, 
            ...
        )
        print(result.confidence_score) # IDE 甚至能自动补全！
        ```

这才是真正的 **"Probabilistic Function"**。它承认内部的不确定性（通过 LLM 思考），但在边界处通过**契约（Schema）**和**协商（Negotiation）**强制实现了确定性。