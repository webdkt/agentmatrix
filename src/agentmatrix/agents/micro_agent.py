"""
Micro Agent: 临时任务专用的轻量级 Agent

设计理念：
- 每个子任务都是一个临时的 Micro Agent
- 简单的 think-negotiate-act 循环
- 无 Session 概念，每次执行都是独立的
- 类似函数调用：输入任务 -> 执行 -> 返回结果
- 通过 parent 参数自动继承父 Agent 的组件
"""

import asyncio
import uuid
import types  # 用于动态绑定
from typing import Dict, List, Optional, Callable, Any, TYPE_CHECKING, Union
import logging
import time

from ..core.log_util import AutoLoggerMixin
from ..core.session_context import SessionContext
from ..core.exceptions import LLMServiceUnavailableError
from ..core.action import register_action
from ..utils.token_utils import estimate_messages_tokens, format_conversation_messages

if TYPE_CHECKING:
    from .base import BaseAgent


class MicroAgent(AutoLoggerMixin):
    """
    临时任务专用的轻量级 Agent

    特点：
    1. 简单的 think-negotiate-act 循环
    2. 直接从 think 输出中识别 action 名字
    3. 通过 cerebellum 协商参数
    4. LLM 自主决定何时返回
    5. 通过 parent 参数自动继承父 Agent 的组件

    设计原则：
    - 所有组件从 parent 继承，简化创建代码
    - 可以通过 parent 链追溯到根 Agent
    """

    def __init__(
        self,
        parent: Union['BaseAgent', 'MicroAgent'],
        name: Optional[str] = None,
        default_max_steps: int = 50,
        independent_session_context: bool = False,
        available_skills: Optional[List[str]] = None,  # 🆕 可用技能列表
    ):
        """
        初始化 Micro Agent

        Args:
            parent: 父级 Agent（BaseAgent 或 MicroAgent）
                - 自动继承 brain, cerebellum, action_registry, logger
                - WorkingContext: 使用指定的上下文
            name: Agent 名称（可选，自动生成）
            default_max_steps: 默认最大步数
            independent_session_context: 是否使用独立的 session context（默认 False）
                - False: 共享 parent 的 session_context（可持久化）
                - True:  创建新的 session_context（不可持久化）
            available_skills: 可用技能列表（如 ["file", "browser"]）
        """
        # 基本信息（必须在动态组合之前设置，因为 _create_dynamic_class 需要 self.name）
        self.name = name or f"MicroAgent_{uuid.uuid4().hex[:8]}"
        self.parent = parent

        # 🆕 动态组合 Skill Mixins（新架构核心）
        if available_skills:
            self.__class__ = self._create_dynamic_class(available_skills)

        # ========== session_context ==========
        # 根据 independent_session_context 决定是共享还是独立
        if independent_session_context:
            # 独立模式：创建新的 SessionContext（不可持久化）
            self._session_context = SessionContext(persistent=False)
        else:
            # 共享模式：使用 parent 的 SessionContext
            self._session_context = parent._session_context

        # ========== 从 parent 自动继承组件 ==========
        self.brain = parent.brain
        self.cerebellum = parent.cerebellum

        # ========== 继承 workspace_root（如果 parent 有）==========
        # 这样 BrowserSkillMixin 等技能可以访问到配置文件路径
        if hasattr(parent, 'workspace_root') and parent.workspace_root:
            self.workspace_root = parent.workspace_root

        # ========== 🆕 扫描所有 actions（新架构）==========
        self.action_registry = {}
        self._scan_all_actions()

        # logger: 直接使用 parent 的 logger（不创建新日志文件）
        self._internal_logger = parent.logger  # 绕过 AutoLoggerMixin 的懒加载

        # ========== 找到根 Agent ==========
        self.root_agent = self._find_root_agent(parent)

        # ========== 其他配置 ==========
        self.default_max_steps = default_max_steps
        self.messages: List[Dict] = []  # 对话历史
        self.run_label: Optional[str] = None  # 执行标识
        self.last_action_name: Optional[str] = None  # 记录最后执行的 action 名字
        self.max_steps = 1024

        # ========== 🆕 压缩相关（默认开启，无需配置）==========
        self.compression_token_threshold = 32000  # 32K tokens
        self.last_compression_step = 0  # 上次压缩时的步数

        # 日志
        self.logger.info(f"MicroAgent '{self.name}' initialized (parent: {parent.name})")

    def get_skill_prompt(self, skill_name: str, prompt_name: str, **kwargs) -> str:
        """
        获取 skill prompt（从 parent Agent）

        为什么 MicroAgent 也需要这个方法：
        - Mixin 的 action 运行时注入到 MicroAgent
        - action 里的 self 是 MicroAgent
        - 但 skill 的其他方法在 Agent 上
        - 统一 API，避免混淆

        Args:
            skill_name: skill 名称
            prompt_name: prompt 名称
            **kwargs: 模板变量

        Returns:
            渲染后的 prompt 字符串

        Raises:
            AttributeError: parent 没有 get_skill_prompt 方法
        """
        # 直接调用 parent 的方法
        return self.parent.get_skill_prompt(skill_name, prompt_name, **kwargs)

    def _find_root_agent(self, parent: Union['BaseAgent', 'MicroAgent']) -> 'BaseAgent':
        """
        递归找到最外层的 BaseAgent

        Args:
            parent: 父级 Agent（可能是 MicroAgent 或 BaseAgent）

        Returns:
            BaseAgent: 最外层的 BaseAgent
        """
        current = parent
        # 沿着 parent 链向上找，直到找不到 parent 属性
        while hasattr(current, 'parent'):
            current = current.parent

        # current 现在是 BaseAgent（没有 parent 属性）
        return current

    def _create_dynamic_class(self, available_skills: List[str]) -> type:
        """
        动态创建包含 Skill Mixins 的类

        Args:
            available_skills: 技能名称列表（如 ["file", "browser", "git_workflow"]）

        Returns:
            type: 动态创建的类

        Example:
            available_skills = ["file", "browser", "git_workflow"]
            返回：type('DynamicAgent_MicroAgent_abc123',
                     (MicroAgent, FileSkillMixin, BrowserSkillMixin),
                     {'_md_skills': [git_workflow_metadata]})
        """
        from ..skills.registry import SKILL_REGISTRY

        # 使用统一的 get_skills() 接口（Lazy Load）
        result = SKILL_REGISTRY.get_skills(available_skills)
        mixin_classes = result.python_mixins
        md_skills = result.md_skills  # 🆕 获取 MD skills

        # 检查加载失败的情况
        if result.failed_skills:
            self.logger.warning(f"  ⚠️  以下 Skills 加载失败: {result.failed_skills}")

        if not mixin_classes and not md_skills:
            self.logger.warning(f"  ⚠️  没有找到可用的 Skills: {available_skills}")
            return self.__class__

        # 记录 Python Mixins 日志
        for mixin in mixin_classes:
            self.logger.debug(f"  🧩 混入 Skill Mixin: {mixin.__name__}")

        # 🆕 记录 MD Skills 日志
        for md_skill in md_skills:
            self.logger.info(f"  📄 加载 MD Skill: {md_skill.skill_name} ({md_skill.display_name})")

        # 动态创建类（Python 的 type 函数）
        # type(name, bases, dict)
        dynamic_class = type(
            f'DynamicAgent_{self.name}',  # 类名
            (self.__class__,) + tuple(mixin_classes),  # 继承链
            {'_md_skills': md_skills}  # 🆕 额外的类属性：存储 MD skills 元数据
        )

        return dynamic_class

    @register_action(
        description="所有任务都已完成。当你觉得没有其他要做的，就必须调用此 action。",
        param_infos={
            "result": "最终结果的描述（可选）"
        }
    )
    async def all_finished(self, result: str = None) -> Any:
        """
        [TERMINAL ACTION] 完成任务并返回最终结果

        这是 MicroAgent 的终止 action，执行后会退出 execute 循环。

        Args:
            result: 任务结果描述（可选）

        Returns:
            Dict: 包含 result 和 finished 标志
        """
        return {"result": result or "", "finished": True}

    def _scan_all_actions(self):
        """
        扫描自身（包括继承链）的所有 @register_action 方法

        由于已经混入了 Skill Mixins，这些方法都在 self 上
        不再需要从 parent 的 actions_map 继承
        """
        import inspect

        # 遍历 self 的类及其所有父类（MRO - Method Resolution Order）
        for cls in self.__class__.__mro__:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, '_is_action') and method._is_action:
                    # 只存储每个 action 一次（最底层的实现）
                    if name not in self.action_registry:
                        # 🔑 关键修复：存储绑定方法（而非未绑定函数）
                        # 这样调用时 self 会自动传递
                        bound_method = getattr(self, name)
                        self.action_registry[name] = bound_method
                        self.logger.debug(f"  ✅ 注册 Action: {name} (来自 {cls.__name__})")

    @property
    def session_folder(self) -> str:
        """便捷访问：根 Agent 的 session_folder"""
        return self.root_agent.get_session_folder()

    def get_session_context(self):
        """
        获取 session context

        Returns:
            SessionContext: session context 对象（可能是共享的或独立的）
        """
        return self._session_context

    async def update_session_context(self, **kwargs):
        """
        更新 session context

        注意：
        - 如果 _session_context 是共享的（来自 BaseAgent），会自动持久化
        - 如果 _session_context 是独立的（不可持久化），只更新内存

        Args:
            **kwargs: 要更新的键值对
        """
        await self._session_context.update(**kwargs)

    # ==================== 🆕 自动压缩机制 ====================

    def _should_compress_messages(self) -> bool:
        """
        判断是否应该压缩 messages（基于 32K tokens）

        Returns:
            bool: 是否应该压缩
        """
        total_tokens = estimate_messages_tokens(self.messages)
        if total_tokens >= self.compression_token_threshold:
            self.logger.info(f"📦 Messages 达到 {total_tokens} tokens，自动压缩...")
            return True
        return False

    async def _generate_whiteboard_summary(self, messages: list,
                                           focus_hint: str = "") -> str:
        """
        LLM 总结：生成 whiteboard（当前状态快照）

        使用液态金属架构（Liquid Metal）：
        - 不固定 Whiteboard 结构
        - 让 LLM 根据对话场景动态生成 Headers
        - 适配任务导向、知识探索、心理咨询、角色扮演等多种场景

        Args:
            messages: 当前对话历史
            focus_hint: 可选，指导 LLM 重点关注某方面

        Returns:
            str: Markdown 格式的 Whiteboard
        """
        from ..utils.parser_utils import whiteboard_parser

        # 注入 Agent Persona（如有）
        persona_hint = ""
        if hasattr(self, 'persona') and self.persona:
            persona_hint = f"""

[Agent Persona Reference]
{self.persona[:800]}

Use this to understand the agent's role and bias your scene diagnosis accordingly.
"""

        # 构造 focus_hint 区块
        focus_hint_block = ""
        if focus_hint:
            focus_hint_block = f"""

# Focus Hint
**重点关注**：{focus_hint}

请在 Whiteboard 中特别突出这方面的信息。
"""

        # 构造 Meta-Prompt（完整版，不简化）
        prompt = f"""
# Role
你是一个高维度的对话状态架构师 (Context Architect)。你的任务不是简单的总结，而是根据对话的**本质类型**，动态构建最适合当前语境的"状态白板 (Whiteboard)"。

# Core Instructions
分析以下对话历史，执行以下三个步骤：
## Step 0: 判断有无现存的“状态白板” (Whiteboard)。如果有，继承他的结构，并在此基础上更新内容(Jump to Step 2B)；如果没有，按照Step 1的思路生成新白板的结构。

## Step 1: 场景识别 (Scene Diagnosis)
判断当前对话的**核心模式**。例如：
- **任务导向 (Task-Oriented)**: 编程、订票、数据分析 -> 需要记录：目标、进度、参数、错误栈...
- **知识探索 (Knowledge-Intensive)**: 教学、头脑风暴、调研 -> 需要记录：核心概念、已验证的事实、待探索的盲区...
- **情感/咨询 (Emotional/Therapeutic)**: 心理咨询、闲聊 -> 需要记录：用户情绪状态、潜在压力源、共情连接点...
- **角色扮演 (Roleplay/Creative)**: 小说创作、游戏 -> 需要记录：当前设定、剧情节点、人物关系、物品栏...


Note: 场景识别是为你服务的，用于构建白板的结构，其内容不需要记录在白板上。你只需要根据识别结果，自然地生成适合的白板结构。

## Step 2A: 结构定义 (Structure Definition)—— 无现有白板时
基于场景识别结果，**动态决定 Whiteboard 的一级标题 (Headers)**。
不要使用固定的模板，让结构自然适配对话内容。

## Step 2B: 结构继承和调整 (Structure Inheritance & Adjustment)—— 有现有白板时
以原有白板为基础，继承结构。快速的根据新的对话内容判断，场景是否发生变化，主题是否发生变化，是否需要对结构进行调整

## Step 3: 状态提取 (State Extraction)
- **去噪**：剔除客套话、重复信息。
- **消歧**：将代词（他/它/那个）还原为实体全名。
- **客观**：只记录事实和结论，不记录流水账。、
- **完整**：保留关键内容和结果，原始目的中不可缺失的部分，后续行动必须持有的线索。

# Output Requirements
1. **必须是 Markdown 格式**
2. **一级标题由你根据 Step 1 动态决定**
3. **必须包含一个通用的 `## 🧠 关键上下文` 或 `## 关键上下文` 区域**，用于兜底非结构化信息
4. 保持简洁：丢弃过时细节、冗余信息、探索过程性信息



{persona_hint}
---

# Conversation History
{format_conversation_messages(messages)}
---
{focus_hint_block}

Start generating the Whiteboard now.
"""

        # 使用 think_with_retry 精确获取 whiteboard
        whiteboard = await self.brain.think_with_retry(
            initial_messages=prompt,
            parser=whiteboard_parser,
            max_retries=3
        )

        return whiteboard  # think_with_retry 直接返回 content (Markdown 字符串)

    async def _compress_messages(self) -> str:
        """
        压缩 messages，保留 system_prompt，添加总结

        新逻辑：
        1. 永远保留第一个 system message（如果有的话）
        2. 找到第一个 user message（原始用户请求）
        3. 检查是否包含 [WHITEBOARD] 标志：
           - 有：替换掉旧 whiteboard（[WHITEBOARD] 之后的内容）
           - 没有：在原始内容后追加新 whiteboard
        4. 结果：[system?, user(原始+新whiteboard)]

        Returns:
            str: 生成的 whiteboard
        """
        # 🆕 压缩前：保存待总结 messages（仅 top-level）
        if self._should_collect_summaries():
            self._push_pending_summary()

        whiteboard = await self._generate_whiteboard_summary(self.messages)

        # ========== 1. 处理 system message ==========
        has_system = self.messages and self.messages[0].get("role") == "system"

        # ========== 2. 找到第一个 user message（原始用户请求）==========
        first_user_msg = None
        for msg in self.messages:
            if msg.get("role") == "user":
                first_user_msg = msg
                break

        if not first_user_msg:
            # 异常情况：没有 user message，创建一个新的
            new_user_content = f"[WHITEBOARD]\n{whiteboard}\n\n请继续执行下一步。"
        else:
            # 正常情况：处理第一个 user message
            original_content = first_user_msg.get("content", "")

            # ========== 3. 检查是否有旧 whiteboard ==========
            if "[WHITEBOARD]" in original_content:
                # 有旧 whiteboard：替换掉（保留 [WHITEBOARD] 之前的内容）
                whiteboard_index = original_content.index("[WHITEBOARD]")
                original_without_old_whiteboard = original_content[:whiteboard_index].strip()
                new_user_content = f"{original_without_old_whiteboard}\n\n[WHITEBOARD]\n{whiteboard}"
            else:
                # 没有旧 whiteboard：追加
                new_user_content = f"{original_content}\n\n[WHITEBOARD]\n{whiteboard}"

        # ========== 4. 重新构建 messages ==========
        if has_system:
            system_msg = self.messages[0]
            self.messages = [
                system_msg,
                {"role": "user", "content": new_user_content}
            ]
        else:
            self.messages = [
                {"role": "user", "content": new_user_content}
            ]

        # 重置计数器
        self.last_compression_step = self.current_step

        return whiteboard

    def _should_collect_summaries(self) -> bool:
        """
        判断是否应该收集待总结内容

        Returns:
            bool: 是否是 top-level MicroAgent
        """
        from .base import BaseAgent
        return isinstance(self.parent, BaseAgent)

    def _push_pending_summary(self):
        """
        推送待总结消息到 root_agent 的队列

        仅 top-level MicroAgent 调用，由 BaseAgent 的 history_worker 处理
        """
        import time

        # 过滤掉 system message（总结不需要 system prompt）
        filtered_messages = [msg.copy() for msg in self.messages if msg.get('role') != 'system']

        summary_item = {
            'messages': filtered_messages,
            'timestamp': time.time(),
            'agent_name': self.name,
            'run_label': self.run_label
        }

        # 推送到 root_agent 的队列
        self.root_agent.pending_summaries_queue.append(summary_item)

        self.logger.debug(
            f"📥 已推送待总结消息到队列 "
            f"(当前队列长度: {len(self.root_agent.pending_summaries_queue)})"
        )

    # ==================== 🆕 自动压缩机制结束 ====================

    async def execute(
        self,
        run_label: str,  # 必须指定，有语义的名字
        persona: str,
        task: str,
        max_steps: Optional[int] = None,
        max_time: Optional[float] = None,
        initial_history: Optional[List[Dict]] = None,
        result_params: Optional[Dict[str, str]] = None,
        yellow_pages: Optional[str] = None,
        session: Optional[Dict] = None,
        session_manager = None,
        simple_mode: bool = False,
        exit_actions = [] # 如果运行哪些动作就退出主循环（all_finished 一定会退出）

    ) -> Any:
        """
        执行任务（可重复调用）

        新架构说明：
        - 不再需要 available_actions 参数
        - 自动使用 action_registry 中的所有 actions（来自初始化时指定的 skills）

        Args:
            run_label: 执行标签（必须），用于日志标识和追踪
            persona: 角色/身份描述（作为 system prompt）
            task: 任务描述
            max_steps: 最大步数（可选，默认使用 default_max_steps）
            max_time: 最大执行时间（分钟）（可选，None 表示不限制时间）
            initial_history: 初始对话历史（用于恢复记忆，可选）
            result_params: 返回值参数描述（可选），用于指定 all_finished 的参数结构
            yellow_pages: 黄页信息（可选），包含其他agent的描述和如何调用它们
            session: session 对象（可选），用于持久化对话历史
            session_manager: session_manager 对象（可选），用于保存 session
            simple_mode: 是否使用简化模式（默认 True)
                          - False: 完整的 system prompt（包含操作环境说明）
                          - True:  简化的 system prompt（只保留 persona + 可用工具）

        Returns:
            Any: 最终结果
                 - 如果 result_params 为 None，返回字符串（向后兼容）
                 - 如果有 result_params，返回 Dict[str, Any]
                 - 如果出错或超时，返回 None 或 {"error": str}
        """
        # ========== 验证参数 ==========
        if not run_label:
            raise ValueError("run_label is required and must be a meaningful name")

        # ========== 设置执行标识 ==========
        self.run_label = run_label

        start_time = time.time()

        # ========== 记录开始 ==========
        self._log(logging.INFO, f"{'='*60}")
        self._log(logging.INFO, f"MicroAgent '{self.run_label}' starting")
        self._log(logging.INFO, f"Task: {task[:200]}{'...' if len(task) > 200 else ''}")

        # 设置本次执行的参数
        self.persona = persona
        self.task = task
        self.yellow_pages = yellow_pages
        self.simple_mode = simple_mode
        self.max_steps = max_steps or self.default_max_steps
        self.max_time = max_time  # 可以是 None

        # 保存 session 和 session_manager 引用
        self.session = session
        self.session_manager = session_manager

        # 🆕 Session 兼容性设置：为了与 BaseAgent 和 Skills 兼容
        # 当 session 参数被提供时，设置与 BaseAgent 相同的属性
        if session:
            self.current_session = session
            self.current_user_session_id = session.get("user_session_id")

            # 创建 SessionContext 对象（如果 session_manager 可用）
            if session_manager and hasattr(session_manager, 'session_context_class'):
                from ..core.session_context import SessionContext
                self._session_context = SessionContext(
                    persistent=True,
                    session_manager=session_manager,
                    session=session,
                    initial_data=session.get("context", {})
                )
            else:
                self._session_context = None

            # 设置 session 文件夹（如果 root_agent 有 workspace_root）
            if self.root_agent and hasattr(self.root_agent, 'workspace_root') and self.root_agent.workspace_root:
                from pathlib import Path
                self.current_session_folder = str(
                    Path(self.root_agent.workspace_root) /
                    session.get("user_session_id", "default") /
                    "history" /
                    (self.root_agent.name if self.root_agent else "unknown") /
                    session.get("session_id", "unknown")
                )
            else:
                self.current_session_folder = None

        # 硬限制：如果都没有设置，最多 1024 步（确保总是会返回）
        if self.max_steps is None and self.max_time is None:
            self.max_steps = 1024
            self._log(logging.INFO, "未设置步数和时间限制，使用硬限制 max_steps=1024")

        # 重置执行状态
        self.step_count = 0
        self.result = None

        # all_finished 现在从 BaseAgent 继承，已在 action_registry 中
        # 动态更新 all_finished 的元数据（如果提供了 result_params）
        if result_params:
            # 获取 all_finished 方法
            all_finished_method = self.action_registry.get("all_finished")  # 注意：这里改为 "all_finished"

            if all_finished_method:
                # 更新参数描述
                all_finished_method._action_param_infos = result_params

                # 动态生成 description，包含参数的自然语言描述
                param_descriptions = ", ".join(result_params.values())
                all_finished_method._action_desc = (
                    f"完成所有任务并返回最终结果。需要提供：{param_descriptions}"
                )

        # 恢复或初始化对话历史
        # 优先从 session 获取，否则使用 initial_history
        if session:
            # 从 session 获取 history
            self.messages = session.get("history", []).copy()
            self._log(logging.INFO, f"Loaded {len(self.messages)} messages from session")
            # 添加新的任务输入
            if len(self.messages) >0:
                self._add_message("user", self._format_task_message())
            else:
                self._initialize_conversation()
        elif initial_history:
            # 恢复记忆：复制历史记录
            self.messages = initial_history.copy()
            self._log(logging.INFO, f"Restoring memory with {len(initial_history)} messages")
            # 添加新的任务输入
            self._add_message("user", self._format_task_message())
        else:
            # 新对话：初始化
            self.messages = []
            self._initialize_conversation()
        self._log(logging.INFO, f"Start to '{self.run_label}' with {len(self.messages)} initial messages")
        self._log(logging.DEBUG, f"Available actions: {list(self.action_registry.keys())}")
        self._log(logging.DEBUG, f"Messages:\n{self._format_messages_for_debug(self.messages)}")

        try:
            # 执行 think-negotiate-act 循环
            await self._run_loop(exit_actions)

            # 计算执行时间
            duration = time.time() - start_time

            # ========== 记录结束 ==========
            self._log(logging.INFO, f"'{self.run_label}' completed in {duration:.2f}s ({self.step_count} steps)")
            self._log(logging.INFO, f"{'='*60}")

            # 返回结果
            return self.result

        except Exception as e:
            duration = time.time() - start_time
            self._log(logging.ERROR, f"'{self.run_label}' failed after {duration:.2f}s")
            self._log(logging.ERROR, f"Error: {str(e)}")
            # 打印完整 traceback 以便调试
            import traceback
            self._log(logging.ERROR, f"Traceback:\n{traceback.format_exc()}")
            return {"error": str(e)}

    def _initialize_conversation(self):
        """初始化对话历史"""
        # 1. System Prompt
        system_prompt = self._build_system_prompt()
        self.messages.append({"role": "system", "content": system_prompt})

        # 2. 任务描述
        task_message = self._format_task_message()
        self.messages.append({"role": "user", "content": task_message})

    def _build_system_prompt(self) -> str:
        """构建 System Prompt"""

        # 简化模式：只保留 persona + 可用工具 + 黄页
        if getattr(self, 'simple_mode', False):
            prompt = f""" {self.persona}

### 可用工具

{self._format_actions_list()}
"""
            # 简化模式下，仍然添加黄页（如果有）
            if self.yellow_pages:
                prompt += f"""### 其他助手

{self.yellow_pages}
"""
            return prompt



        

        # 完整模式（默认）：包含操作环境说明
        prompt = f"""### 运行时环境 (Runtime Environment)

你是一个运行在 **AgentMatrix 架构** 中的 **智能体 (Autonomous Agent)**。
你的思维存在于一个持续的 **循环 (Loop)** 中：`感知 (Observe) -> 思考 (Think) -> 行动 (Act)`。

#### 1. 认知与记忆 (Cognition & Memory)
*   **上下文 (Context)**: 你拥有完整的对话历史和 **Whiteboard (状态白板)**。这是你的短期记忆。
*   **无状态工具 (Stateless Tools)**: 你的工具（Actions）是**无状态**的函数。它们**看不到**你的对话历史或 Whiteboard。
    *   ❌ 错误调用: `search_web("extact the budget from above")` (工具不知道 "above" 是什么)
    *   ✅ 正确调用: `search_web("Alpha Project budget 2024")` (显式传递完整参数)

#### 2. 交互协议 (Interaction Protocol)
*   **显式意图**: 不要含糊其辞。你的每一个 Action 都必须有明确的目的。
*   **参数完备**: 调用 Action 时，必须自行从上下文中提取所有必要参数。如果参数缺失，**先向用户提问**，不要瞎编。
*   **单步与并行**: 
    *   如果任务复杂，请拆解为多个步骤。
    *   如果多个步骤互不依赖（如搜索两个不同的关键词），请在一个 `[ACTIONS]` 块中同时发出，以并行加速。

---
### 🧰 可用工具箱 (Toolbox)

#### A. 核心指令 (Native Actions)
这些是你原本就具备的能力：
{self._format_actions_list()}
"""

        # 🆕 添加 MD Document Skills 摘要
        md_skills_summary = self._format_md_skills_summary()
        if md_skills_summary:
            prompt += f"""#### B. 扩展技能库 (Procedural Skills)
你拥有以下任务的标准操作程序 (SOP)。当遇到相关任务时，优先使用 `read` 获取详细步骤：

{md_skills_summary}

"""

        # 如果提供了黄页信息，添加黄页部分
        if self.yellow_pages:
            prompt += f"""#### C. 协作网络 (Collaborators)
如果你无法独立完成任务，可以联系以下 Agent。请使用 `send_email` 

{self.yellow_pages}
"""

        prompt += """
        ---
### 响应协议 (Response Protocol)

请按照以下自然分块格式进行回复。

**1. 思考块**
使用 `[THOUGHTS]` 标签开始。
在这里尽情思考，分析 Whiteboard，拆解任务。这是你的草稿纸，不需要拘泥于格式。

**2. 行动块**
使用 `[ACTIONS]` 标签开始。
#### 输出样例
```
[THOUGHTS]
你的想法和意图，这是给你自己的，工具看不到，不需要担心格式，只要清晰表达思考过程和下一步计划即可

[ACTIONS]
为实现意图而立刻要做的动作（只能从可用动作里选择，例如send_email），并提供完成该动作需要的全部信息。
如果要做多个动作，必须是可以并行执行、互不依赖的动作。
```
"""

        return prompt



    def _format_actions_list(self) -> str:
        """格式化可用 actions 列表（直接使用 action_registry）"""
        lines = []
        # 遍历 action_registry 中的所有 actions（来自初始化时指定的 skills）
        for action_name, method in self.action_registry.items():
            # 尝试获取描述
            desc = getattr(method, "_action_desc", "No description")
            lines.append(f"- {action_name}: {desc}")
        return "\n".join(lines)

    def _format_md_skills_summary(self) -> str:
        """
        格式化 MD Document Skills 摘要（用于 system prompt）

        显示格式：
        - **显示名称**: 简要描述
          完整文档: SKILLS/{skill_name}/skill.md
        """
        # 获取 MD skills（从 skill load result 中）
        md_skills = getattr(self, '_md_skills', [])

        if not md_skills:
            return ""

        lines = []
        for skill_meta in md_skills:
            # 显示名称 + 摘要
            lines.append(f"- **{skill_meta.display_name}**: {skill_meta.brief_summary}")
            # 文档路径（相对于 workspace）
            if skill_meta.workspace_path:
                doc_path = f"SKILLS/{skill_meta.skill_name}/skill.md"
                lines.append(f"  完整文档: `{doc_path}`")

            # 列出可用的 Actions
            if skill_meta.actions:
                action_names = [action.name for action in skill_meta.actions]
                lines.append(f"  包含操作: {', '.join(action_names)}")

            lines.append("")  # 空行分隔

        return "\n".join(lines)


    def _format_task_message(self) -> str:
        """格式化任务消息"""
        #msg = f"[💡NEW SIGNAL]\n{self.task}\n"

        #return msg
        return self.task

    def _format_messages_for_debug(self, messages: List[Dict]) -> str:
        """
        格式化 messages 列表为人类友好的调试输出

        Args:
            messages: 消息列表，每条消息包含 role 和 content

        Returns:
            格式化后的字符串，如：
            system: ...
            user: ...
            assistant: ...
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # 截取前 3000 字符，避免输出过长
            preview = content[:3000] + "..." if len(content) > 3000 else content

            # 转换为更易读的格式
            lines.append(f"{role}: {preview}")

        return "\n".join(lines)

    async def _run_loop(self, exit_actions=[]):
        """执行主循环 - 支持批量 action 执行和时间限制，添加 LLM 服务异常处理"""
        start_time = time.time()
        if isinstance(exit_actions, str):
            exit_actions = [exit_actions]
        # 确定最大步数（可能为 None，表示只受时间限制）
        max_steps = self.max_steps
        step_count = 0

        # 将分钟转换为秒
        max_time_seconds = self.max_time * 60 if self.max_time else None

        while True:
            # 🔀 检查点1：每次循环开始时检查是否暂停
            await self.root_agent._checkpoint()

            # 检查步数限制
            if step_count >= max_steps:
                self.logger.warning(f"达到最大步数 ({max_steps})")
                self.result = "未完成，达到最大步数限制，最后的状态如下：\n" + self.result
                break

            # 🆕 检查是否需要自动压缩（基于 32K tokens）
            if self._should_compress_messages():
                await self._compress_messages()

            # 检查时间限制
            if max_time_seconds:
                elapsed = time.time() - start_time
                if elapsed >= max_time_seconds:
                    self.logger.warning(f"达到最大时间 ({self.max_time}分钟)，已执行 {step_count} 步")
                    self.result = "未完成，达到最大时间限制，最后的状态如下：\n" + self.result
                    break

            step_count += 1
            self.step_count = step_count

            # 计算已用时间（用于日志）
            elapsed = time.time() - start_time if max_time_seconds else 0
            step_info = f"Step {step_count}"
            if max_steps:
                step_info += f"/{max_steps}"
            if self.max_time:
                elapsed_minutes = elapsed / 60
                step_info += f" (时间: {elapsed_minutes:.1f}分钟/{self.max_time}分钟)"
            self.logger.debug(step_info)

            # 🔀 检查点2：think 之前检查是否暂停
            await self.root_agent._checkpoint()

            try:
                # 1. Think（使用 think_with_retry + actions parser）
                thought = await self.brain.think_with_retry(
                    initial_messages = self.messages,
                    parser=self._parse_actions_from_thought,
                    action_registry=self.action_registry,
                    max_retries=3
                )
                print(thought)
                action_thought = thought["[ACTIONS]"]
                raw_reply = thought.get("[RAW_REPLY]")
                

                #self.logger.debug(f"THOUGHTS: {raw_reply}")  
                #self.logger.debug(f"ACTIONS: {action_thougth}") 


                # 2. 检测 actions（多个，保持顺序）
                action_names = await self._detect_actions(action_thought)

                self.logger.debug(f"Detected actions: {action_names}")

                # 3. 记录 assistant 的思考（只记录一次）
                self._add_message("assistant", raw_reply )

                # 5. 顺序执行所有 actions
                execution_results = []
                should_break_loop = False  # 标记是否需要退出主循环

                for idx, action_name in enumerate(action_names, start=1):
                    # 🔀 检查点3：每个 action 执行前检查是否暂停
                    if hasattr(self, 'root_agent') and self.root_agent and hasattr(self.root_agent, '_checkpoint'):
                        await self.root_agent._checkpoint()

                    # === 处理特殊 actions ===
                    if action_name == "all_finished":
                        # 执行 all_finished
                        result = await self._execute_action("all_finished", action_thought, idx, action_names)
                        self.result = result
                        self.return_action_name = "all_finished"
                        should_break_loop = True
                        # 不记录 execution_results，直接退出
                        break  # ← 退出 for action_names 循环

                    elif action_name == "update_memory":
                        # 执行 update_memory（特殊处理：不记录结果，因为它压缩 messages）
                        await self._execute_action("update_memory", action_thought, idx, action_names)
                        self.logger.debug(f"✅ {action_name} done (messages compressed)")
                        # 不记录到 execution_results（action 已内部处理）
                        # 不退出循环，继续下一轮

                    elif action_name in exit_actions:
                        # rest_n_wait 不需要执行，直接等待
                        self.return_action_name = action_name
                        should_break_loop = True
                        break  # ← 退出 for action_names 循环

                    # === 执行普通 actions ===
                    else:
                        try:
                            result = await self._execute_action(action_name, action_thought, idx, action_names)
                            if result!="NOT_TO_RUN":
                                execution_results.append(f"[{action_name} Done]:\n {result}")
                            self.logger.debug(f"✅ {action_name} done")
                            self.logger.debug(result)

                        except Exception as e:
                            error_msg = str(e)
                            execution_results.append(f"[{action_name} Failed]:\n {error_msg}")
                            self.logger.warning(f"❌ {action_name} failed: {error_msg}")

                # 6. 反馈给 Brain（只有普通 actions 才反馈）
                if execution_results:
                    combined_result = "\n".join(execution_results)

                    # Hook：子类可重写来增强反馈
                    enhanced_feedback = await self._prepare_feedback_message(
                        combined_result,
                        step_count,
                        start_time
                    )

                    self._add_message("user", enhanced_feedback)

                    self.result = combined_result #有进展就保存一下，最后的结果，下面如果超时或者超轮次退出，就用这个未完成结果。

                # 7. 检查是否需要退出主循环
                if should_break_loop:
                    break

            except LLMServiceUnavailableError as e:
                # ========== LLM 服务异常处理 ==========
                self.logger.warning(
                    f"⚠️  LLM service error in step {step_count}: {str(e)}"
                )

                # 等待一小段时间（3秒），确保 monitor 完成至少一次检查
                # monitor 最多 60 秒检查一次，但通常服务故障会很快被发现
                self.logger.debug("Waiting for monitor to update service status...")
                await asyncio.sleep(3)

                # 检查服务状态
                if self._is_llm_available():
                    # 服务已恢复，重试当前步骤
                    self.logger.info("✅ Service recovered, retrying current step")
                    step_count -= 1  # 抵消上面的 +=1，重新执行这一步
                    continue

                # 服务确实不可用，进入等待模式
                self.logger.warning("🔄 Service still unavailable, entering wait mode...")
                await self._wait_for_llm_recovery()

                # 恢复后重试当前步骤
                self.logger.info("✅ Service recovered after wait, retrying current step")
                step_count -= 1  # 抵消上面的 +=1，重新执行这一步
                continue

    def _is_llm_available(self) -> bool:
        """
        检查 LLM 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        # 向后兼容：如果没有 runtime，假设服务可用
        if not hasattr(self.root_agent, 'runtime') or self.root_agent.runtime is None:
            return True

        # 通过 runtime 访问 monitor
        monitor = self.root_agent.runtime.llm_monitor
        if monitor is None:
            return True

        return monitor.llm_available.is_set()

    async def _wait_for_llm_recovery(self):
        """等待 LLM 服务恢复（轮询方式）"""
        monitor = self.root_agent.runtime.llm_monitor
        if monitor is None:
            # 如果没有 monitor，直接返回
            return

        check_interval = 5  # 每 5 秒检查一次
        waited_seconds = 0

        self.logger.info("⏳ Waiting for LLM service recovery...")

        while True:
            await asyncio.sleep(check_interval)
            waited_seconds += check_interval

            # 检查是否恢复
            if monitor.llm_available.is_set():
                self.logger.info(f"✅ LLM service recovered after {waited_seconds}s")
                break

            # 每 30 秒打印一次日志
            if waited_seconds % 30 == 0:
                self.logger.warning(
                    f"⏳ Still waiting for LLM service... ({waited_seconds}s elapsed)"
                )

    async def _prepare_feedback_message(
        self,
        combined_result: str,
        step_count: int,
        start_time: float
    ) -> str:
        """
        准备反馈消息（Hook 方法）

        子类可以重写此方法来增强反馈（如添加时间提示）

        Args:
            combined_result: 所有 action 的执行结果
            step_count: 当前步数
            start_time: 循环开始时间

        Returns:
            反馈消息字符串
        """
        return f"[💡Body Feedback]:\n {combined_result}"

    def _parse_actions_from_thought(self, raw_reply: str, action_registry: dict) -> dict:
        """
        Parser for think_with_retry - 验证 LLM 输出是否包含有效的 action 声明

        规则：
        1. 如果有 [ACTIONS] section → 检查下面是否有有效的 action name
           - 有 → 返回 raw_reply（验证通过）
           - 没有 → 返回 error（让 LLM 重试）
        2. 如果没有 [ACTIONS] section → 检查全文是否只提到一个 action
           - 是 → 返回 raw_reply（验证通过）
           - 否则 → 返回 error（让 LLM 重试）

        Args:
            raw_reply: LLM 的原始输出
            action_registry: 可用的 actions 注册表

        Returns:
            {
                "status": "success" | "error",
                "content": raw_reply (success 时) | None (error 时),
                "feedback": str (error 时)
            }
        """
        import re

        # 规则1：检查是否有 [ACTIONS] section
        if "[ACTIONS]" in raw_reply:
            # 提取 [ACTIONS] 下的内容
            from ..skills.parser_utils import multi_section_parser

            result = multi_section_parser(
                raw_reply,
                section_headers=["[ACTIONS]"],
                match_mode="ANY"
            )

            if result["status"] == "success":
                actions_text = result["content"]["[ACTIONS]"]
                
                


                # 检查是否包含有效的 action（使用正则提取，参照 _extract_mentioned_actions 的方法）
                import re
                action_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)'
                matches = re.finditer(action_pattern, actions_text)

                detected_actions = set()
                for match in matches:
                    action_name = match.group(1).lower()
                    if action_name in action_registry:
                        detected_actions.add(action_name)

                if detected_actions:
                    # 验证通过：[ACTIONS] 下有有效的 action
                    result["content"]["[RAW_REPLY]"] = raw_reply
                    return result
                else:
                    # 验证失败：[ACTIONS] 下没有有效的 action
                    return {
                        "status": "error",
                        "feedback": f"[ACTIONS] 下必须要指明使用什么动作(action 名字)"
                    }
            else:
                # multi_section_parser 失败
                return {
                    "status": "error",
                    "feedback": "必须在[ACTIONS] 下指明使用什么动作(action 名字)"
                }
        

        # 规则2：没有 [ACTIONS] section，检查全文是否只提到一个 action
        # 正则提取所有 action names
        action_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)'
        matches = re.finditer(action_pattern, raw_reply)

        detected_actions = set()
        for match in matches:
            action_name = match.group(1).lower()
            if action_name in action_registry:
                detected_actions.add(action_name)

        # 检查数量
        if len(detected_actions) == 1:
            # 只有一个 action，验证通过
            content = {
                "[ACTIONS]": raw_reply,
                "[RAW_REPLY]": raw_reply
            }
            return {"status": "success", "content": content}
        
        else:
            # 多个 actions，但没有用 [ACTIONS] section
            return {
                "status": "error",
                "feedback": "必须使用 [ACTIONS] section 来明确列出要执行的动作"
            }

    

    def _extract_mentioned_actions(self, thought: str) -> List[str]:
        """
        使用正则表达式提取用户**提到**的所有 action（完整单词匹配）

        注意：
        - 这个方法只是提取"提到的"actions，不是"要执行的"actions
        - 最终要执行哪些actions需要由小脑进一步判断
        - 保留重复出现的 action（支持多次执行同一个 action）

        Example:
            "我刚做完了web_search，现在准备file_operation" → ["web_search", "file_operation"]
            "使用send_email发送" → ["send_email"]
            "先搜索，然后完成" → ["web_search", "all_finished"]
            "write A, write B, write C" → ["write", "write", "write"]
        """
        import re

        # 正则：匹配连续的字母、下划线、数字（标识符格式）
        # [a-zA-Z_]: 必须以字母或下划线开头
        # [a-zA-Z0-9_]*: 后续可以是字母、数字、下划线
        action_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)'

        # 提取所有匹配的字符串
        matches = re.finditer(action_pattern, thought)

        # 按出现顺序记录 (position, action_name)
        detected = []

        for match in matches:
            action_name = match.group(1)
            position = match.start()

            # 转小写（action names 通常是 snake_case）
            action_name_lower = action_name.lower()

            # 只保留有效的 action names（在 action_registry 中）
            if action_name_lower in self.action_registry:
                detected.append((position, action_name_lower))

        # 按出现位置排序
        detected.sort(key=lambda x: x[0])

        # 返回 action 名称列表（保留重复和顺序）
        return [action for _, action in detected]

    def _parse_and_validate_actions(
        self,
        raw_reply: str,
        mentioned_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Parser: 提取并验证要执行的 actions

        流程：
        1. 使用 multi_section_parser 提取 [ACTIONS]
        2. 解析 action 列表（保留重复，支持多次执行同一个 action）
        3. 验证：防止幻觉（必须在 mentioned_actions 中）
        4. 验证：必须可用（在 available_actions 中）

        Args:
            raw_reply: LLM 的原始输出
            mentioned_actions: 阶段1提取到的"提到的actions"

        Returns:
            dict: {"status": "success", "content": [action_names]}
                  或 {"status": "error", "feedback": str}
        """
        from ..skills.parser_utils import multi_section_parser

        # 1. 提取 [ACTIONS] section
        result = multi_section_parser(
            raw_reply,
            section_headers=["[ACTIONS]"],
            match_mode="ALL"
        )

        if result["status"] == "error":
            return result

        # 2. 解析 actions 列表（保留重复，不去重）
        actions_text = result["content"]["[ACTIONS]"]
        # 先整体清理：去除换行符、回车符、代码块标记、各种引号括号
        for char in ['\n', '\r', '```', '"', "'", '`', '(', ')', '[', ']', '{', '}']:
            actions_text = actions_text.replace(char, '')
        actions_text = actions_text.strip()
        # 再分割
        actions_list = [a.strip() for a in actions_text.split(',')]

        # 3. 验证：防止幻觉（必须在 mentioned_actions 中）
        invalid_actions = [a for a in actions_list if a not in mentioned_actions]
        if invalid_actions:
            return {
                "status": "error",
                "feedback": (
                    f"你返回了未被提到的 actions: {invalid_actions}。\n"
                    f"只能从用户提到的 actions 中选择: {mentioned_actions}\n\n"
                    f"请重新判断，只选择用户**真正要执行**的 actions。"
                )
            }

        # 4. 不再需要验证是否在 available_actions 中
        # 因为 mentioned_actions 已经通过 _extract_tool_calls() 过滤为只在 action_registry 中的 actions

        return {"status": "success", "content": actions_list}

    async def _detect_actions(self, thought: str) -> List[str]:
        """
        两阶段检测：判断用户真正要执行的 actions

        阶段 1：使用正则提取"提到的 actions"
        阶段 2：问小脑哪些是"真正要执行的"

        这样可以避免误匹配，例如：
        - "我刚做完了 action_a，现在准备 action_b"
        - 阶段1提取：[action_a, action_b]
        - 阶段2判断：[action_b]（只选择要执行的）

        Args:
            thought: Brain 的思考内容

        Returns:
            List[str]: 真正要执行的 action 名称列表
        """
        # ========== 阶段 1：提取"提到的 actions" ==========
        mentioned_actions = self._extract_mentioned_actions(thought)

        if not mentioned_actions:
            # 没有提到任何 action
            return []

        # 如果只提到了一个 action，直接返回（避免不必要的 LLM 调用）
        if len(mentioned_actions) == 1:
            self.logger.debug(f"[阶段1] 只提到一个 action: {mentioned_actions[0]}")
            return mentioned_actions

        # ========== 阶段 2：问小脑哪些要执行 ==========
        self.logger.debug(f"[阶段1] 提到的 actions: {mentioned_actions}")

        # 构造 prompt
        prompt = f"""用户刚才说了：

{thought}

从这段话中，依次提到了这些 actions：
{', '.join(mentioned_actions)}

请判断：这些 actions 中，哪些是**真正要执行**的？

**注意：**
- 如果要做多个action，必须按用户指定的顺序列出来, 
- 在[ACTIONS]下列出所有要执行的 actions，用逗号分隔，保持顺序，不要因为名字相同就合并成一个。


**输出格式：**
```
(可选的）whatever you thinks...
[ACTIONS]
action1, action2, action3
```

**示例：**
输入：我刚做完了 web_search，现在准备 write plan.txt ,send_mail给老板，然后再write report.txt
（注意，有多个 write，保持顺序）
输出：
```
[ACTIONS]
write, send_mail, write
```
"""

        # 使用小脑的 think_with_retry
        actions_to_execute = await self.cerebellum.backend.think_with_retry(
            initial_messages=[{"role": "user", "content": prompt}],
            parser=self._parse_and_validate_actions,
            mentioned_actions=mentioned_actions,  # 直接传参给 parser
            max_retries=3
        )

        self.logger.debug(f"[阶段2] 判断要执行的 actions: {actions_to_execute}")
        return actions_to_execute

    async def _execute_action(
        self,
        action_name: str,
        thought: str,
        action_index: int,
        action_list: List[str]
    ) -> Any:
        """
        执行 action（新架构：直接调用，无需动态绑定）

        流程：
        1. 从 action_registry 获取方法（已经在 self 上）
        2. 通过 cerebellum 解析参数（带任务上下文）
        3. 直接调用方法（self 已经正确指向最终的 MicroAgent 实例）

        关键改进：不再需要 types.MethodType 动态绑定

        Args:
            action_name: 要执行的 action 名称
            thought: Brain 的思考内容（用户意图）
            action_index: 当前是第几个 action（从 1 开始）
            action_list: 完整的 action 列表
        """
        # 1. 获取方法（已经在 self 上，无需绑定）
        if action_name not in self.action_registry:
            raise ValueError(f"Action '{action_name}' not found in registry")

        method = self.action_registry[action_name]

        # 2. 获取参数信息（从 method）
        param_schema = getattr(method, "_action_param_infos", {})

        # 3. 如果有参数，通过 cerebellum 解析
        if param_schema:
            # 计算当前 action 的出现次数（第几个这个 action）
            occurrence = action_list[:action_index].count(action_name)
            total_same_actions = action_list.count(action_name)

            # 智能构造任务上下文：只有当 action 重复出现时才添加详细信息
            if total_same_actions > 1:
                task_context = f"""
(第 {occurrence} 个: {action_name} Action
**注意：用户一共提到 {total_same_actions} 次去做 '{action_name}'，这是其中的第 {occurrence} 次{action_name} 。**

"""
                if action_index > 0:
                    previous_actions = action_list[:action_index]
                    task_context = task_context + f"它排在{previous_actions} 后面"
                else:
                    task_context = task_context + "它是第一个要执行的 action"
            else:
                # action 只出现一次，不需要额外的上下文信息（保持简洁）
                task_context = f"Action: {action_name} "

            # 通过 cerebellum 解析参数（带任务上下文）
            async def brain_clarification(question: str) -> str:
                temp_msgs = self.messages.copy()
                temp_msgs.append({"role": "assistant", "content": thought})
                temp_msgs.append({"role": "user", "content": f"[❓NEED CLARIFICATION] {question}"})
                response = await self.brain.think(temp_msgs)
                return response['reply']

            action_json = await self.cerebellum.parse_action_params(
                intent=thought,
                action_name=action_name,
                param_schema=param_schema,
                brain_callback=brain_clarification,
                task_context=task_context  # 新增：传递任务上下文
            )

            params = action_json.get("params", {})
            if params == "NOT_TO_RUN":
                return params
        else:
            params = {}

        # 3. 执行方法（✅ 直接调用，无需动态绑定）
        self._log(logging.DEBUG, f"[{self.run_label}] Executing {action_name} (task {action_index}/{len(action_list)})")
        result=""

        try:
            # 💬 特殊处理：ask_user action
            if action_name == "ask_user":
                if not hasattr(self, 'root_agent') or not self.root_agent:
                    raise RuntimeError("ask_user requires root_agent")

                question = params.get("question", "")
                if not question:
                    raise ValueError("ask_user requires 'question' parameter")

                # 调用 root_agent.ask_user（会挂起等待用户输入）
                result = await self.root_agent.ask_user(question)
            else:
                # 普通 action：正常调用
                result = await method(**params)
        except Exception as e:
            result = f"Error executing {action_name}: {str(e)}"
        finally:

        # 记录最后执行的 action 名字
            self.last_action_name = action_name

        return result

    def _add_message(self, role: str, content: str):
        """
        添加消息到对话历史

        如果有 session，自动保存到 session
        """
        self.messages.append({"role": role, "content": content})

        # 如果有 session，自动保存
        if self.session and self.session_manager:
            self.session["history"] = self.messages.copy()
            # 创建异步任务来保存（不阻塞主流程）
            asyncio.create_task(self.session_manager.save_session(self.session))

    def get_history(self) -> List[Dict]:
        """
        获取完整的对话历史

        Returns:
            List[Dict]: 完整的对话历史（包括初始历史 + 新增对话）
        """
        return self.messages

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {
            "label": self.run_label or "unknown",
            "name": self.name
        }
