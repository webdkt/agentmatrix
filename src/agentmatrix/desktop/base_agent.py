import asyncio
from typing import Dict, Optional, Callable, List, Any, Tuple, Union
from dataclasses import dataclass, asdict, field
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from .session_manager import SessionManager
import traceback
import inspect
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
from ..core.agent_shell import AgentShell
import logging
from pathlib import Path
from ..core.micro_agent import MicroAgent


@dataclass
class EmailSignal:
    """邮件信号 — Desktop 层实现，遵循 Signal 协议。"""
    sender: str
    recipient: str
    subject: str
    body: str
    attachments: list = field(default_factory=list)
    email_ids: list = field(default_factory=list)

    @property
    def signal_type(self) -> str:
        return "email"

    @property
    def signal_id(self) -> Optional[str]:
        # 邮件信号用 email_ids 作为可靠投递标识
        return ",".join(self.email_ids) if self.email_ids else None

    def to_text(self) -> str:
        text = f"[新邮件] 来自 {self.sender}: {self.subject}\n{self.body}"
        if self.attachments:
            text += "\n" + "\n".join(
                f"附件已保存在 {att.get('container_path', att.get('filename', ''))}"
                for att in self.attachments
            )
        return text

    def log_detail(self) -> Dict[str, Any]:
        return {
            "signal_type": "email",
            "email_ids": self.email_ids,
            "sender": self.sender,
        }


# Agent 状态常量
class AgentStatus:
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class AskUserQuestion:
    """ask_user 问题数据结构（增强版）

    支持图片附件、选项按钮（单选/多选）、自定义输入
    """
    question: str                        # 问题文本
    options: Optional[List[str]] = None  # 选项列表（单选/多选）
    multiple: bool = False               # 是否多选（False=单选，True=多选）
    image_path: Optional[str] = None     # 图片路径（容器内路径，复制后会更新为文件名）

    def to_dict(self) -> dict:
        """转换为字典（用于 WebSocket 传输）"""
        return {
            "question": self.question,
            "options": self.options,
            "multiple": self.multiple,
            "image_path": self.image_path
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'AskUserQuestion':
        """从字典创建实例"""
        # 兼容旧格式：如果 data 是字符串，直接作为 question
        if isinstance(data, str):
            return cls(question=data)
        # 新格式：包含 question 字段的对象
        return cls(
            question=data.get("question", ""),
            options=data.get("options"),
            multiple=data.get("multiple", False),
            image_path=data.get("image_path")
        )


class BaseAgent(AutoLoggerMixin, AgentShell):
    _log_from_attr = "name"  # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG

    def __init__(self, profile, profile_path: str = None):
        from ..core.skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.add_search_path("agentmatrix.desktop.skills")

        self.name = profile["name"]
        self.description = profile["description"]
        self.profile_path = profile_path  # 配置文件路径（用于 ConfigService 定位）

        # persona 直接是字符串
        self.persona = profile.get("persona", "")

        # 加载其他 prompts（如 task_prompt）
        self.other_prompts = profile.get("prompts", {})

        # Prompt 模板缓存
        self._prompt_cache = {}

        self.profile = profile
        self.backend_model = profile.get("backend_model", "default_llm")

        # 🆕 新架构：读取 skills 配置
        self.skills = profile.get("skills", [])
        self.brain = None
        self.cerebellum = None
        self.vision_brain = None  # 🆕 视觉大模型（支持图片理解的LLM）

        self._status = AgentStatus.IDLE  # 🔧 私有变量，只能通过 update_status 修改
        from datetime import datetime

        self._status_since = datetime.now()  # 状态变化的时间

        # 📊 状态历史（最近 10 条，用于前端查询）
        self.status_history = []
        self._max_status_history = 10  # 🔧 扩展到 10 条

        self.last_received_email = None  # 最后收到的信
        self.post_office = None

        # Session Manager（延迟初始化）
        self.session_manager = None

        # 标准组件
        self.inbox = asyncio.Queue()

        # 事件回调 (Server 注入)
        self.async_event_callback: Optional[Callable] = None

        # Runtime 引用 (由 AgentMatrix 注入)
        self._runtime = None

        # ✨ 新架构：使用 action_registry 代替 actions_map
        self.action_registry = {}  # name -> bound_method (新架构)
        self.actions_meta = {}  # name -> metadata (给小脑看)
        self.current_session = None
        self.current_task_id = None
        self.current_user_session_id = None  # 🆕 当前用户会话ID（如果邮件来自User）

        # 🔧 广播消息的回调（由 runtime 注入）
        self._broadcast_message_callback = None

        # 扫描 BaseAgent 自身的 actions（不包含 skills）
        self._scan_all_actions()

        # 🔀 暂停/恢复机制
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为已设置（不阻塞）

        # 🛑 停止机制
        self._stopped = False
        self._stop_event = asyncio.Event()
        self._stop_event.set()  # 初始状态为已设置（不阻塞）

        # 💬 ask_user 机制（等待用户输入）
        self._pending_user_question = None  # 当前等待用户回答的问题
        self._user_input_future = None  # 用于等待用户输入的 Future

        # 🆕 双 Worker 模型（email_worker + history_worker）
        self.pending_summaries_queue = []  # 待总结的消息块队列
        self.email_worker_task = None  # email worker 引用
        self.history_worker_task = None  # history worker 引用

        # 🆕 Stop 机制
        self._execute_task = None  # 当前正在运行的 execute task
        self._is_stopping = False  # 是否正在停止

        # 🆕 信号驱动架构 — session 管理
        self.active_session_id: Optional[str] = None
        self.active_micro_agent: Optional[MicroAgent] = None
        self._session_task: Optional[asyncio.Task] = None
        self.waiting_emails: List[Email] = []  # 非 active session 的邮件暂存

        # 🐳 Container Session（延迟初始化）
        self.container_session = None

        # 🌐 浏览器适配器（懒启动，Agent 级共享资源）
        self._browser_adapter = None

        # 🆕 Collab Mode（运行时状态，不持久化）
        self.collab_mode: bool = False
        self._collab_output_loop: Optional[asyncio.AbstractEventLoop] = None
        self.current_collab_file: Optional[str] = None  # 当前协作的文件路径
        self._last_deactivated_session_id: Optional[str] = None  # 上一次停用的 session_id

        # 🆕 记录最后一次 top-level MicroAgent 执行的 system prompt
        self.last_system_prompt = None

        self.logger.info(f"Agent {self.name} 初始化完成")

        # ✨ 新架构：Skills 改为 Lazy Load（通过 SKILL_REGISTRY 自动发现）
        # 不再需要手动注册，移除 _register_new_skills() 方法

    def _init_container_session(self):
        """初始化 Container Session"""
        if self.runtime is None:
            raise RuntimeError("runtime 未注入，无法初始化 Container Session")

        if (
            not hasattr(self.runtime, "container_manager")
            or not self.runtime.container_manager
        ):
            raise RuntimeError("container_manager 未初始化，无法获取 Container Session")

        cm = self.runtime.container_manager

        # 确保用户存在（创建 Linux 用户和目录）
        cm.ensure_user(self.name)

        # 获取或创建 container session
        self.container_session = cm.get_container_session(self.name)
        self.logger.info(
            f"Container Session 初始化成功 (session_id: {self.container_session.session_id})"
        )

        # 始终挂载 output mirror，让终端输出持续广播
        self._setup_output_mirror()

    async def switch_workspace(self, task_id: str) -> bool:
        """切换工作目录（通过 container session 执行命令）"""
        if self.container_session is None:
            raise RuntimeError("Container Session 未初始化")

        # 1. 在宿主机创建目录（使用 runtime.paths）
        task_dir = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        # 2. 在容器内更新软链接（Agent 用户可以操作自己的软链接，不需要 root）
        # ~/current_task 是固定的软链接，指向当前任务目录
        # 先删除旧的 symlink 再创建，避免部分容器环境（如 BusyBox）下 ln -sf 不替换已有 symlink 的问题
        symlink_target = f"/data/agents/{self.name}/work_files/{task_id}"
        cmd = f"rm -f ~/current_task && ln -s {symlink_target} ~/current_task && cd ~/current_task && readlink -f ~/current_task"
        self.logger.info(f"🔧 switch_workspace 命令: {cmd}")
        self.logger.info(f"🔧 宿主机目录存在: {task_dir.exists()}")
        exit_code, stdout, stderr = await asyncio.to_thread(
            self.container_session.execute, cmd
        )
        if exit_code != 0:
            self.logger.warning(f"switch_workspace 命令失败: exit={exit_code}, stderr={stderr}")
            return False

        self.logger.info(f"工作目录已切换: {self.name} -> {task_id}")
        self.logger.info(f"🔍 symlink 实际指向: {stdout.strip() if stdout else 'unknown'}")
        return True

    # ==================== 浏览器管理 ====================

    def get_browser(self):
        """
        获取浏览器适配器（懒创建，不启动浏览器进程）

        浏览器进程在首次 ensure_browser_started() 时启动。
        返回的 adapter 是 Agent 级共享资源，所有 MicroAgent 共用同一个 Chrome 实例。

        Returns:
            DrissionPageAdapter: 浏览器适配器实例
        """
        if self._browser_adapter is not None:
            return self._browser_adapter

        from .browser.drission_page_adapter import DrissionPageAdapter

        profile_path = str(self.runtime.paths.get_browser_profile_dir(self.name))
        self._browser_adapter = DrissionPageAdapter(profile_path=profile_path)
        self.logger.info(f"🌐 浏览器适配器已创建 (profile: {profile_path})")
        return self._browser_adapter

    async def ensure_browser_started(self):
        """确保浏览器进程已启动（仅首次调用时实际启动）"""
        adapter = self.get_browser()
        if adapter.browser is None:
            await adapter.start(headless=False)
            self.logger.info("🌐 浏览器进程已启动")

    # ==================== Collab Mode ====================

    def _setup_output_mirror(self):
        """
        设置 container session 的 output mirror → WebSocket 广播

        reader thread 是同步线程，不能直接调 asyncio 代码。
        使用 asyncio.run_coroutine_threadsafe() 安全地调度协程。
        """
        if not self.container_session:
            return

        self._collab_output_loop = asyncio.get_event_loop()

        def _on_output(stream_type: str, line_text: str):
            """在 reader thread 中同步调用"""
            if not self._broadcast_message_callback:
                return
            loop = self._collab_output_loop
            if loop and loop.is_running():
                msg = {
                    "type": "COLLAB_BASH_OUTPUT",
                    "agent_name": self.name,
                    "data": {"stream": stream_type, "line": line_text},
                }
                coro = self._broadcast_message_callback(msg)
                asyncio.run_coroutine_threadsafe(coro, loop)

        self.container_session.set_output_callback(_on_output)
        self.logger.info("📡 Output mirror 已启用")

    def _teardown_output_mirror(self):
        """取消 container session 的 output mirror"""
        if self.container_session:
            self.container_session.set_output_callback(None)
        self._collab_output_loop = None
        self.logger.info("📡 Output mirror 已关闭")

    

    

    @property
    def runtime(self):
        return self._runtime

    @runtime.setter
    def runtime(self, value):
        self._runtime = value  # 注意：必须用 _runtime，否则会递归
        if value is not None:
            # 初始化SessionManager（使用 runtime.paths）
            self.session_manager = SessionManager(
                agent_name=self.name, matrixpath=self.runtime.paths,
                db=self.post_office.email_db,
            )

            # 🐳 初始化 Container Session（在 workspace_root 设置后）
            if self.container_session is None:
                self._init_container_session()

    def get_prompt_template(self, name: str) -> str:
        """获取 prompt 模板（AgentShell 接口实现）"""
        return self.runtime.prompt_registry.get(name)

    def render_template(self, template: str, **overrides) -> str:
        """渲染模板：自动用 self 属性替换 $variable，支持手动覆盖。

        占位符格式: $variable_name（字母、数字、下划线）
        替换优先级: overrides > self 属性 > 不替换（保留原文）

        Example:
            self.render_template(template)  # 自动替换 self.persona 等
            self.render_template(template, yellow_pages_section="...")  # 额外替换
        """
        import re

        def replacer(match):
            key = match.group(1)
            if key in overrides:
                return str(overrides[key])
            if hasattr(self, key):
                val = getattr(self, key)
                return str(val) if val is not None else match.group(0)
            return match.group(0)  # 保留原文

        return re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', replacer, template)

    async def generate_working_notes(
        self,
        messages: list,
        focus_hint: str = "",
        scratchpad: list = None,
        is_top_level: bool = False,
    ) -> str:
        """从对话历史生成 Working Notes（AgentShell 接口实现）。

        使用液态金属架构（Liquid Metal）：不固定结构，让 LLM 根据对话场景动态生成 Headers。

        Args:
            messages: 当前对话历史
            focus_hint: 可选，指导 LLM 重点关注某方面
            scratchpad: 工作过程中的自留笔记列表
            is_top_level: 是否是顶层 Agent（有邮件历史的场景）
        """
        from ..core.utils.parser_utils import working_notes_parser
        from ..core.utils.token_utils import format_session_messages

        # 注入 Agent Persona（如有）
        persona_hint = ""
        if self.persona:
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

请在 Working Notes 中特别突出这方面的信息。
"""

        # 构造 scratchpad 区块
        scratchpad_block = ""
        if scratchpad:
            items = "\n".join(f"- {s}" for s in scratchpad)
            scratchpad_block = f"""
# Scratchpad (工作过程中的自留笔记)
以下是工作过程中随手记录的要点，可能与 Session History 有重复，但它们标记了你认为重要的信息：
{items}

---
"""

        # Top-level 和 Nested 的分层指引不同
        if is_top_level:
            step_2_5 = """## Step 2.5: Working Notes 用途意识 (Purpose Awareness)

Working Notes 的读者是你自己——下一轮循环中继续工作的你。

对话历史中，邮件记录始终可读（Email History will always be there）。
你不需要担心沟通内容丢失或走样，也不需要在 Working Notes 中重述已经通过邮件表达过的内容。
专注于**如何帮助自己记住对后续工作有必要的东西**。

白问自己：下一轮醒来，你需要立刻知道什么才能接着干？

信息天然分层：
- **沟通层**（目标、计划、承诺、状态更新）→ 邮件已覆盖，Working Notes 不必重复
- **执行层**（做了什么、调用了什么、文件在哪里）→ Working Notes 的核心
- **发现层**（数据长什么样、遇到什么技术约束、搜索到了什么）→ Working Notes 的核心
- **调整层**（原计划如何、实际为何调整、踩了什么坑）→ Working Notes 的核心"""

            step_3 = """## Step 3: 状态提取 (State Extraction)
- **去噪**：剔除客套话、重复信息。
- **消歧**：将代词（他/它/那个）还原为实体全名。
- **客观**：只记录事实和结论，不记录流水账。
- **聚焦**：侧重执行层、发现层、调整层的信息。沟通层信息如果在邮件中已经完整记录，无需重复。
- **完整**：保留继续工作所需的线索——文件路径、中间产物位置、技术决策原因、未完成的子任务。"""

            output_extra = """5. **写完后自问**：这些信息是否能帮助我下一轮立刻接着干？如果某些信息在 Email History 中已经清晰可查，考虑是否需要保留。"""
        else:
            step_2_5 = ""

            step_3 = """## Step 3: 状态提取 (State Extraction)
- **去噪**：剔除客套话、重复信息。
- **消歧**：将代词（他/它/那个）还原为实体全名。
- **客观**：只记录事实和结论，不记录流水账。
- **完整**：保留关键内容和结果，原始目的中不可缺失的部分，后续行动必须持有的线索。"""

            output_extra = ""

        # 构造 Meta-Prompt
        prompt = f"""
# Role
你是一个高维度的对话状态架构师 (Context Architect)。你的任务不是简单的总结，而是根据对话的**本质类型**，动态构建最适合当前语境的"工作笔记 (Working Notes)"。

# Core Instructions
分析以下对话历史，执行以下步骤：
## Step 0: 判断有无现存的"工作笔记" (Working Notes)。如果有，继承他的结构，并在此基础上更新内容(Jump to Step 2B)；如果没有，按照Step 1的思路生成新的结构。

## Step 1: 场景识别 (Scene Diagnosis)
判断当前对话的**核心模式**。例如：
- **任务导向 (Task-Oriented)**: 编程、订票、数据分析 -> 需要记录：目标、进度、参数、错误栈...
- **知识探索 (Knowledge-Intensive)**: 教学、头脑风暴、调研 -> 需要记录：核心概念、已验证的事实、待探索的盲区...
- **情感/咨询 (Emotional/Therapeutic)**: 心理咨询、闲聊 -> 需要记录：用户情绪状态、潜在压力源、共情连接点...
- **角色扮演 (Roleplay/Creative)**: 小说创作、游戏 -> 需要记录：当前设定、剧情节点、人物关系、物品栏...


Note: 场景识别是为你服务的，用于构建结构，其内容不需要记录在笔记中。你只需要根据识别结果，自然地生成适合的结构。

## Step 2A: 结构定义 (Structure Definition)—— 无现有笔记时
基于场景识别结果，**动态决定 Working Notes 的一级标题 (Headers)**。
不要使用固定的模板，让结构自然适配对话内容。

## Step 2B: 结构继承和调整 (Structure Inheritance & Adjustment)—— 有现有笔记时
以原有笔记为基础，继承结构。快速的根据新的对话内容判断，场景是否发生变化，主题是否发生变化，是否需要对结构进行调整

{step_2_5}

{step_3}

# Output Requirements
1. **必须是 Markdown 格式**
2. **一级标题由你根据 Step 1 动态决定**
3. **必须包含一个通用的 `## 🧠 关键上下文` 或 `## 关键上下文` 区域**，用于兜底非结构化信息
4. 保持简洁：丢弃过时细节、冗余信息、探索过程性信息
{output_extra}



{persona_hint}
---
{scratchpad_block}
# Session History
{format_session_messages(messages)}
---
{focus_hint_block}

Start generating the Working Notes now.
"""

        working_notes = await self.brain.think_with_retry(
            initial_messages=prompt, parser=working_notes_parser, max_retries=3
        )

        return working_notes

    async def compress_messages(self, agent) -> None:
        """压缩 agent 的 messages（AgentShell 接口实现）。

        Desktop 实现：top-level 使用邮件历史 + working notes，nested 使用原始 user message + working notes。
        """
        is_top_level = agent.is_top_level

        # 生成 working notes
        working_notes = await self.generate_working_notes(
            agent.messages,
            scratchpad=agent.scratchpad,
            is_top_level=is_top_level,
        )

        # 剥掉 working_notes 开头可能带的 [WORKING NOTES]
        if working_notes and "[WORKING NOTES]" in working_notes:
            import re
            working_notes = re.sub(
                r'\[WORKING NOTES\]\s*\n*', '', working_notes, count=1
            ).strip()

        # 写入 session event
        session_id = agent.session.get("session_id") if agent.session else None
        if session_id:
            await self._log_session_event(session_id, "session", "message_auto_compress", {
                "step_count": agent.step_count,
                "working_notes_preview": working_notes if working_notes else None,
            })

        # 保留 system message
        has_system = agent.messages and agent.messages[0].get("role") == "system"

        # 构建新的 user message content
        if is_top_level:
            # === Top-level: 使用邮件历史 ===
            try:
                emails = await self.post_office.get_emails_by_session(
                    session_id=agent.session["session_id"],
                    agent_name=self.name,
                )
                agent.logger.debug(f"📧 已加载 {len(emails)} 封邮件")
                email_history = self._format_email_history(emails)
                new_user_content = f"{email_history}\n\n[WORKING NOTES]\n{working_notes}"
            except Exception as e:
                agent.logger.warning(f"⚠️ 获取邮件历史失败，降级到原有逻辑: {e}")
                new_user_content = self._build_fallback_user_content(agent, working_notes)
        else:
            # === Nested: 原始 user message + working notes ===
            new_user_content = self._build_fallback_user_content(agent, working_notes)

        # 重建 messages
        if has_system:
            agent.messages = [agent.messages[0], {"role": "user", "content": new_user_content}]
        else:
            agent.messages = [{"role": "user", "content": new_user_content}]

        # 保存到 session
        if agent.session and agent.session_manager:
            agent.session["history"] = agent.messages
            await agent.session_manager.save_session(agent.session)

        # 清空 scratchpad
        agent.scratchpad.clear()

    def _build_fallback_user_content(self, agent, working_notes: str) -> str:
        """构建默认的 user message content（原始 user message + working notes）。"""
        first_user_msg = None
        for msg in agent.messages:
            if msg.get("role") == "user":
                first_user_msg = msg
                break

        if not first_user_msg:
            return f"[WORKING NOTES]\n{working_notes}\n\n请继续执行下一步。"

        original_content = first_user_msg.get("content", "")
        if "[WORKING NOTES]" in original_content:
            import re
            notes_index = original_content.index("[WORKING NOTES]")
            original_without_old_notes = original_content[:notes_index].strip()
            return f"{original_without_old_notes}\n\n[WORKING NOTES]\n{working_notes}"
        else:
            return f"{original_content}\n\n[WORKING NOTES]\n{working_notes}"

    def _format_email_history(self, emails) -> str:
        """格式化邮件历史为聊天风格文本。"""
        from ..core.micro_agent_utils import format_email_history
        return format_email_history(emails, self.name)

    # ========== MD Skill 管理 ==========

    def _load_md_skills(self) -> dict:
        """扫描 Agent 的 SKILLS 目录，返回 {skill_name: description} 字典"""
        try:
            skills_dir = self.runtime.paths.get_agent_skills_dir(self.name)
            if not skills_dir.exists():
                return {}

            skills = {}
            for item in skills_dir.iterdir():
                if not item.is_dir():
                    continue

                # 查找 skill.md（不区分大小写）
                skill_md_path = None
                for file in item.iterdir():
                    if file.is_file() and file.name.upper() == "SKILL.MD":
                        skill_md_path = file
                        break

                if skill_md_path is None:
                    continue

                description = self._read_skill_description(skill_md_path)
                skills[item.name] = description

            return skills

        except Exception as e:
            self.logger.warning(f"Failed to load md skills: {e}")
            return {}

    @staticmethod
    def _read_skill_description(skill_md_path) -> str:
        from ..core.utils import micro_agent_utils as _utils
        return _utils.read_skill_description(skill_md_path)

    @staticmethod
    def _build_md_skill_section_from_dict(md_skills: dict) -> str:
        """从 md_skills dict 生成扩展技能库文本段"""
        if not md_skills:
            return ""

        lines = [
            "#### B. 扩展技能库 (Procedural Skills)",
            f"你有{len(md_skills)}个额外扩展技能存放在 `~/SKILLS/` 目录。每个子目录对应一个技能，目录内包含 skill.md 描述文件。",
            "如果需要使用扩展技能，先列目录，看有什么技能（目录名代表了技能的名字）",
            "如果名字看上去可能是你需要的，就继续读里面的 skill.md 的开头，判断是否真的是你需要的技能",
            "如果是需要的技能，就继续阅读，理解如何使用。扩展技能的命令通常要通过 bash 执行",
            "",
            "可用扩展技能：",
        ]
        for skill_name, description in md_skills.items():
            lines.append(f"- **{skill_name}**: {description}")

        return "\n".join(lines)

    @property
    def status(self):
        """只读属性：必须通过 update_status() 方法来修改"""
        return self._status

    # ========== 暂停/恢复机制 ==========

    async def pause(self):
        """暂停 Agent 执行"""
        if self._paused:
            self.logger.warning(f"Agent {self.name} 已经是暂停状态")
            return

        self._paused = True
        self._pause_event.clear()  # 清除事件，导致 await 会阻塞
        self.logger.info(f"⏸️ Agent {self.name} 已暂停")

        # 🔧 更新状态并推送
        self.update_status(new_status=AgentStatus.PAUSED)

    async def resume(self):
        """恢复 Agent 执行（用于 pause 恢复）"""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self.logger.info(f"▶️ Agent {self.name} 从暂停状态恢复")
            self.update_status(new_status=AgentStatus.IDLE)
        else:
            self.logger.warning(f"Agent {self.name} 未暂停")

    async def _checkpoint(self):
        """
        检查点：在 MicroAgent 的关键位置调用

        如果 Agent 处于停止或暂停状态，会挂起当前协程，直到恢复。
        """
        if self._stopped:
            self.logger.debug(f"🛑 Agent {self.name} 检查到停止，等待恢复...")
            await self._stop_event.wait()
            self.logger.debug(f"✅ Agent {self.name} 从停止状态恢复")
        if self._paused:
            self.logger.debug(f"🛑 Agent {self.name} 检查到暂停，等待恢复...")
            await self._pause_event.wait()
            self.logger.debug(f"✅ Agent {self.name} 已恢复执行")

    @property
    def is_paused(self) -> bool:
        """返回 Agent 是否暂停"""
        return self._paused

    # ========== Stop 机制 ==========

    def stop(self):
        """
        停止 Agent：取消当前 active session。

        Agent 继续运行 main loop，新邮件到达时会自动触发新的 session 处理。
        """
        self._is_stopping = True

        # 取消所有 running action tasks
        if self.active_micro_agent:
            entries = dict(self.active_micro_agent._running_actions)
            self.active_micro_agent._running_actions.clear()
            for aid, info in entries.items():
                task = info["task"] if isinstance(info, dict) else info
                task.cancel()

        # 取消 session task
        if self._session_task and not self._session_task.done():
            self._session_task.cancel()
            self.logger.info(f"🛑 Agent {self.name} 已停止当前 session")

        self.update_status(new_status=AgentStatus.STOPPED)

    # ========== ask_user 机制 ==========

    async def ask_user(
        self,
        question: Union[str, AskUserQuestion],
        **kwargs
    ) -> str:
        """
        等待用户输入（增强版）

        此方法会挂起当前 MicroAgent 的执行，等待用户通过 submit_user_input 提供答案。
        同时支持全局暂停机制。

        Args:
            question: 向用户提出的问题（str）或 AskUserQuestion 对象
            **kwargs: 可选参数（用于扩展）
                - options: List[str] - 选项列表（单选/多选）
                - multiple: bool - 是否多选（默认 False）
                - image_path: str - 图片路径（容器内路径）

        Returns:
            str: 用户的回答（单选值、多选值逗号分隔、或自定义文本）

        Example:
            # 简单文本问题
            answer = await self.ask_user("请确认预算范围")
            # 返回: "5万-10万"

            # 单选问题
            answer = await self.ask_user(
                question="请选择预算范围",
                options=["5万以下", "5-10万", "10万以上"],
                multiple=False
            )
            # 返回: "5-10万"

            # 多选问题
            answer = await self.ask_user(
                question="请选择功能模块",
                options=["用户管理", "数据分析", "报表生成"],
                multiple=True
            )
            # 返回: "用户管理,数据分析"

            # 带图片的问题
            answer = await self.ask_user(
                question="请分析图表",
                image_path=str(self.private_workspace / "chart.png")
            )
            # 返回: "呈现上升趋势"
        """
        from datetime import datetime
        import shutil

        # 🔧 参数标准化（统一转换为 AskUserQuestion 对象）
        if isinstance(question, str):
            # 简单格式：纯文本问题
            question_obj = AskUserQuestion(
                question=question,
                options=kwargs.get('options'),
                multiple=kwargs.get('multiple', False),
                image_path=kwargs.get('image_path')
            )
        elif isinstance(question, AskUserQuestion):
            # 已是 AskUserQuestion 对象
            question_obj = question
        else:
            raise TypeError(f"question 必须是 str 或 AskUserQuestion，当前类型: {type(question)}")

        # 🔧 记录旧状态并设置新状态
        old_status = self._status  # 保存旧状态

        # ✅ 处理图片文件（复制到 attachments 目录）
        session_id = (
            self.current_session.get("session_id")
            if self.current_session
            else self.current_task_id
        )

        if question_obj.image_path:
            source_path = Path(question_obj.image_path)
            if source_path.exists():
                try:
                    # 复制到当前 session 的 attachments 目录
                    att_dir = self.runtime.paths.get_agent_attachments_dir(
                        self.name, session_id
                    )
                    att_dir.mkdir(parents=True, exist_ok=True)

                    filename = source_path.name
                    dest_path = att_dir / filename

                    # 复制文件
                    shutil.copy2(source_path, dest_path)

                    # 更新为文件名（供前端 API 使用）
                    question_obj.image_path = filename

                    self.logger.info(f"✅ 图片已复制到 attachments: {filename}")
                except Exception as e:
                    self.logger.warning(f"⚠️ 复制图片失败: {e}，将忽略图片")
                    question_obj.image_path = None
            else:
                self.logger.warning(f"⚠️ 图片不存在: {source_path}，将忽略图片")
                question_obj.image_path = None

        # 3. 记录问题（给 API 查询）
        self._pending_user_question = question_obj

        # 确保 current_user_session_id 不为 None（用于前端匹配会话）
        if not self.current_user_session_id and self.current_task_id:
            self.current_user_session_id = self.current_task_id

        # 🔧 更新状态会触发 AGENT_STATUS_UPDATE 增量推送（包含 pending_question）
        self.update_status(new_status=AgentStatus.WAITING_FOR_USER)

        # ✅ 发送邮件通知（如果 runtime 可用）
        task_id = self.current_task_id
        await self._send_ask_user_email(question_obj, task_id, session_id)

        # 4. 创建 Future 并挂起
        self._user_input_future = asyncio.Future()

        question_preview = question_obj.question[:50]
        if len(question_obj.question) > 50:
            question_preview += "..."

        self.logger.info(f"💬 向用户提问: {question_preview}")

        try:
            # 发起提问前，先确保当前没有被暂停
            await self._checkpoint()

            # 🔧 修复：直接 await Future，不使用 wait_for（避免 Future 被取消）
            # 无限期挂起，直到前端调用 submit_user_input(answer) 触发 set_result(answer)
            answer = await self._user_input_future

            # 拿到答案后，再次检查是否在等待期间系统被暂停了
            await self._checkpoint()

            answer_preview = answer[:50] if len(answer) > 50 else answer
            self.logger.info(f"✅ 收到用户回答: {answer_preview}")
            return answer

        finally:
            # 🔧 恢复状态
            self.update_status(new_status=old_status)
            self._pending_user_question = None
            self._user_input_future = None
            # 🔧 移除：状态清理（避免内存泄漏）
            # 注：不再需要显式清理，因为 finally 已经处理

    async def _send_ask_user_email(self, question: AskUserQuestion, task_id: str, session_id: str):
        """
        发送 ask_user 邮件通知

        当 Agent 调用 ask_user 时，发送一封特殊邮件给用户，
        用户可以直接回复邮件来回答问题。

        Subject 格式：请回答问题 #ASK_USER#{agent_name}#{agent_session_id}#

        Args:
            question: AskUserQuestion 对象（包含问题、选项、图片等信息）
            task_id: 任务ID
            session_id: Agent session ID
        """
        if not self.runtime:
            self.logger.warning("⚠️ runtime 未注入，跳过 ask_user 邮件发送")
            return

        try:
            # 获取 Email Proxy Service
            email_proxy = self.runtime.email_proxy
            if not email_proxy:
                self.logger.warning(
                    "⚠️ Email Proxy Service 未找到，跳过 ask_user 邮件发送"
                )
                return

            # 直接调用 EmailProxyService 的专用方法
            await email_proxy.send_ask_user_email(
                agent_name=self.name,
                agent_session_id=session_id,
                question=question
            )

            self.logger.info(f"✅ 已发送 ask_user 邮件通知: {question[:50]}...")
        except Exception as e:
            self.logger.error(f"❌ 发送 ask_user 邮件失败: {e}", exc_info=True)

    async def submit_user_input(self, answer: str, session_id: str):
        """
        提交用户输入（由 Server API 调用）

        此方法会唤醒正在等待的 ask_user 调用，并传入用户的回答。

        Args:
            answer: 用户的回答

        Raises:
            RuntimeError: 如果 Agent 当前没有在等待用户输入

        Example:
            # 在 Server API 中
            await agent.submit_user_input("5万-10万")
        """
        if (
            not self.current_session
            or self.current_session.get("session_id") != session_id
        ):
            # not for this session
            return
        if not self._user_input_future or self._user_input_future.done():
            return

        self.logger.debug(
            f"📥 提交用户回答: {answer[:50]}{'...' if len(answer) > 50 else ''}"
        )

        # 设置结果，唤醒 Future
        self._user_input_future.set_result(answer)

    def get_status_snapshot(self) -> dict:
        """
        获取当前 Agent 的完整状态快照

        Returns:
            dict: Agent 完整状态，包含：
                - status: Agent 状态
                - pending_question: 等待中的用户问题（AskUserQuestion 对象或 None）
                - current_session_id: 当前会话 ID
                - current_task_id: 当前任务 ID
                - current_user_session_id: 当前用户会话 ID
                - status_history: 状态历史（最近 10 条）
        """
        user_session_id = self.current_user_session_id
        if not user_session_id and self.current_task_id:
            user_session_id = self.current_task_id

        # 🔧 处理 pending_question 的序列化
        pending_question = None
        if hasattr(self, "_pending_user_question") and self._pending_user_question:
            if isinstance(self._pending_user_question, AskUserQuestion):
                # 新格式：AskUserQuestion 对象
                pending_question = self._pending_user_question.to_dict()
            elif isinstance(self._pending_user_question, str):
                # 兼容旧格式：纯文本
                pending_question = self._pending_user_question
            else:
                # 其他情况（不应该发生）
                pending_question = str(self._pending_user_question)

        return {
            "status": self._status,
            "pending_question": pending_question,
            "current_session_id": self.current_session.get("session_id")
            if self.current_session
            else None,
            "current_task_id": self.current_task_id,
            "current_user_session_id": user_session_id,
            "status_history": self.status_history.copy(),
            "current_collab_file": self.current_collab_file,
        }

    def update_status(self, new_status=None):
        """
        统一的状态更新接口（唯一修改 Agent 状态的方式）

        Args:
            new_status (str, optional): 新的 Agent 状态

        注意：此方法会触发增量状态推送
        """
        if new_status is not None:
            self._status = new_status
            from datetime import datetime

            self._status_since = datetime.now()
            self.logger.debug(f"📊 Status: {new_status}")

        if self._broadcast_message_callback:
            agent_info = self.get_status_snapshot()
            message = {
                "type": "AGENT_STATUS_UPDATE",
                "agent_name": self.name,
                "data": agent_info,
            }
            asyncio.create_task(self._send_message(message))

    async def _send_message(self, message):
        """异步发送消息（数据已经在调用方准备好）"""
        try:
            await self._broadcast_message_callback(message)
        except Exception as e:
            self.logger.warning(f"Failed to send status update: {e}")

    async def _log_session_event(self, session_id: str, event_type: str, event_name: str, event_detail: dict = None):
        """异步写入 session 事件 + WebSocket 广播"""
        from datetime import datetime
        # DB 写入
        detail_str = json.dumps(event_detail, ensure_ascii=False) if event_detail else None
        await self.post_office.email_db.insert_session_event(
            owner=self.name,
            session_id=session_id,
            event_type=event_type,
            event_name=event_name,
            event_detail=detail_str,
        )
        # WebSocket 广播
        if self._broadcast_message_callback:
            message = {
                "type": "SESSION_EVENT",
                "agent_name": self.name,
                "session_id": session_id,
                "data": {
                    "event_type": event_type,
                    "event_name": event_name,
                    "event_detail": event_detail,
                    "timestamp": datetime.now().isoformat(),
                }
            }
            asyncio.create_task(self._broadcast_message_callback(message))

    def get_current_status(self) -> dict:
        """获取当前状态（最新一条）"""
        if self.status_history:
            return self.status_history[-1]
        return {"message": "空闲", "timestamp": None}

    def get_status_history(self) -> list:
        """获取状态历史（最近 10 条）"""
        return self.status_history.copy()

    def _scan_all_actions(self):
        """
        扫描所有 actions（新架构）

        扫描自身及其父类的所有 @register_action 方法，
        并存储到 action_registry（已绑定的方法）。
        """
        import inspect

        for cls in self.__class__.__mro__:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, "_is_action") and method._is_action:
                    # 只存储第一次遇到的（避免重复）
                    if name not in self.action_registry:
                        # 存储已绑定的方法（直接可调用）
                        self.action_registry[name] = getattr(self, name)

                        # 提取元数据
                        desc = method._action_desc
                        param_infos = method._action_param_infos

                        self.actions_meta[name] = {
                            "action": name,
                            "description": desc,
                            "params": param_infos,
                        }

    @property
    def private_workspace(self) -> Path:
        """
        获取当前 session 的个人工作目录（如果不存在则自动创建）

        Returns:
            Path: 个人工作目录路径
        """
        if self.runtime is None:
            return None

        task_id = self.current_task_id or "default"
        # 通过 runtime.paths 获取路径
        workspace = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    @property
    def current_workspace(self) -> Path:
        """
        获取当前 session 的共享工作目录（如果不存在则自动创建）

        Returns:
            Path: 共享工作目录路径
        """
        if self.runtime is None:
            return None

        task_id = self.current_task_id or "default"
        # 通过 runtime.paths 获取路径
        workspace = self.runtime.paths.workspace_dir / task_id / "shared"

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    async def emit(self, event_type, content, payload={}):
        """
        发送事件到注册的事件回调函数

        Args:
            event_type (str): 事件的类型，用于标识不同种类的事件,

            content (str): 事件的主要内容描述
            payload (dict, optional): 事件的附加数据，默认为None，当为None时会使用空字典

        Returns:
            None

        Raises:
            无显式抛出异常
        """
        # 检查是否存在事件回调函数
        if self.async_event_callback:
            # 创建新的事件对象，包含事件类型、发送者名称、内容和附加数据
            event = AgentEvent(event_type, self.name, self.status, content, payload)
            # 异步调用事件回调函数，将事件对象传递过去
            await self.async_event_callback(event)

    async def run(self):
        """主循环：启动 _main_loop + history_worker"""
        self.email_worker_task = asyncio.create_task(self._main_loop())
        self.history_worker_task = asyncio.create_task(self._history_worker())

        await self.emit("SYSTEM", f"{self.name} Started")

        try:
            await asyncio.gather(self.email_worker_task, return_exceptions=True)
        except asyncio.CancelledError:
            self.logger.info(f"{self.name} main loop cancelled")
            if self.email_worker_task:
                self.email_worker_task.cancel()
            if self.history_worker_task:
                self.history_worker_task.cancel()
            try:
                await asyncio.gather(
                    self.email_worker_task,
                    self.history_worker_task,
                    return_exceptions=True,
                )
            except Exception:
                pass
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error in {self.name} main loop")

    async def _main_loop(self):
        """
        主循环：收邮件 + 路由 + session 管理

        替代旧的 _email_worker + process_email。
        邮件不再阻塞处理，而是路由到 active session 的 signal_queue，
        或暂存到 waiting_emails 等待后续 session 处理。
        """
        self.logger.info("🔄 Main loop 已启动")

        try:
            while True:
                # 暂停状态：阻塞等待 resume
                if self._paused:
                    self.logger.info("⏸️ Main loop 已暂停，等待恢复...")
                    await self._pause_event.wait()
                    self.logger.info("▶️ Main loop 已恢复")

                # 阻塞等待邮件
                email = await self.inbox.get()

                try:
                    self.last_received_email = email
                    await self._route_email(email)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.exception(f"Error routing email in {self.name}")
                finally:
                    self.inbox.task_done()

        except asyncio.CancelledError:
            # 取消 session task
            if self._session_task and not self._session_task.done():
                # 取消所有 running action tasks
                if self.active_micro_agent:
                    for aid, task in self.active_micro_agent._running_actions.items():
                        task.cancel()
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            self.logger.info("🔄 Main loop 已停止")
            raise

    async def _route_email(self, email: Email):
        """
        路由邮件到正确的 session。

        三种情况：
        1. 无 active session → activate session 并投递邮件
        2. active session + 邮件属于同一 session → 投递到 signal_queue
        3. active session + 邮件属于不同 session → 暂存到 waiting_emails
        """
        # 解析 session
        session = await self.session_manager.get_session(email)
        session_id = session["session_id"]

        # 更新 recipient_session_id
        if email.recipient_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                recipient_session_id=session_id,
                receiver_name=self.name,
            )

        # 📝 写入 session event: email.received（记录原始邮件内容）
        body_preview = email.body[:200] if email.body else ""
        await self._log_session_event(
            session_id=session_id,
            event_type="email",
            event_name="received",
            event_detail={
                "email_ids": [email.id],
                "sender": email.sender,
                "recipient": email.recipient,
                "subject": email.subject or "",
                "body_preview": body_preview,
                "has_more": bool(email.body and len(email.body) > 200),
                "attachments": email.attachments or [],
                "task_id": email.task_id,
            },
        )

        if self.active_session_id is None:
            # 情况 1：无 active session → activate
            await self._activate_session(session, email)
        elif self.active_session_id == session_id:
            # 情况 2：同一 session → 投递 batch 信号
            if self.active_micro_agent:
                self.active_micro_agent.signal_queue.put_nowait(
                    EmailSignal(
                        sender=email.sender,
                        recipient=email.recipient,
                        subject=email.subject,
                        body=email.body,
                        attachments=email.attachments or [],
                        email_ids=[email.id],
                    )
                )
            self.logger.debug(f"📧 邮件路由到 active session {session_id[:8]}")
        else:
            # 情况 3：不同 session → 暂存
            self.waiting_emails.append(email)
            self.logger.debug(
                f"📧 邮件暂存 (session {session_id[:8]} != active {self.active_session_id[:8]})"
            )

    async def _activate_session(self, session: dict, first_email: Email):
        """
        激活 session：创建 MicroAgent，投递首封邮件，启动 session task。
        """
        session_id = session["session_id"]
        self.active_session_id = session_id
        self.current_session = session
        self.current_task_id = session["task_id"]
        # 只在真正切换到不同 session 时才清空 collab file
        # 同一 session re-activate（如等待用户输入后继续）应保留 collab file
        if self._last_deactivated_session_id != session_id:
            self.current_collab_file = None

        # 设置 current_user_session_id
        if self.runtime and first_email.sender == self.runtime.get_user_agent_name():
            self.current_user_session_id = first_email.sender_session_id
        else:
            self.current_user_session_id = None

        # 切换工作区
        if self.container_session is None:
            raise RuntimeError("Container Session 未初始化。")
        # 重建 container shell（deactivate 时已 stop，这里按需 start）
        if not self.container_session.is_alive():
            self.logger.info(f"🔌 重建 container shell: {self.container_session.session_id}")
            self.container_session.start()
        success = await self.switch_workspace(session["task_id"])
        if not success:
            self.logger.error(f"工作区切换失败: task_id={session['task_id']}, container_alive={self.container_session.is_alive()}")
            raise RuntimeError(f"工作区切换失败: {session['task_id']}")

        # 准备 available_skills
        available_skills = self.profile.get("skills", [])
        for required in ["base", "email"]:
            if required not in available_skills:
                available_skills = [required] + available_skills

        # 预组装 system prompt 模板（Shell 选模板、填变量）
        template_key = "COLLAB_MODE" if getattr(self, "collab_mode", False) else "SYSTEM_PROMPT"
        template_str = self.render_template(
            self.get_prompt_template(template_key),
            user_name=self.runtime.user_agent_name,
            agent_name=self.name,
            yellow_pages_section=self.post_office.yellow_page_exclude_me(self.name) or "",
        )

        # 加载 md skills
        md_skills = self._load_md_skills()

        # 创建 MicroAgent
        micro_agent = MicroAgent(
            parent=self, name=self.name, available_skills=available_skills,
            system_prompt=template_str, md_skills=md_skills,
        )
        self.active_micro_agent = micro_agent

        # 首封邮件作为 signal 放入 queue
        micro_agent.signal_queue.put_nowait(EmailSignal(
            sender=first_email.sender,
            recipient=first_email.recipient,
            subject=first_email.subject,
            body=first_email.body,
            attachments=first_email.attachments or [],
            email_ids=[first_email.id],
        ))

        # 启动 session task — task 为空，邮件通过 signal 进入
        self._session_task = asyncio.create_task(
            self._run_session(micro_agent, session)
        )
        self.logger.info(f"🚀 Session {session_id[:8]} 已激活")

        # 📝 写入 session event: session.activated
        await self._log_session_event(
            session_id=session_id,
            event_type="session",
            event_name="activated",
            event_detail={"task_id": session.get("task_id"), "original_sender": session.get("original_sender")},
        )

    async def _run_session(self, micro_agent: MicroAgent, session: dict):
        """
        运行 session 的 MicroAgent，处理完成后的清理。
        """
        session_id = session["session_id"]

        async def _consume_events():
            """消费 Core event queue，处理 DB 持久化、WebSocket 广播、邮件标记已读等。"""
            while True:
                try:
                    event = await micro_agent.event_queue.get()
                except asyncio.CancelledError:
                    break

                if event.event_type == "status":
                    # 状态事件：只更新状态
                    self.update_status(new_status=event.event_name.upper())

                elif event.event_type == "signal" and event.event_name == "processed":
                    # 信号处理完成：提取 signal_id 标记已读（如邮件），不广播
                    signals = event.detail.get("signals", [])
                    signal_ids = [s.signal_id for s in signals if s.signal_id]
                    if signal_ids:
                        try:
                            await self.post_office.email_db.mark_emails_processed(signal_ids)
                        except Exception as e:
                            self.logger.warning(f"mark_emails_processed failed: {e}")

                elif event.event_type == "signal":
                    # signal/received 等内部事件，忽略
                    pass

                else:
                    # 其他事件：写入 session event + WebSocket 广播
                    await self._log_session_event(
                        session_id=session_id,
                        event_type=event.event_type,
                        event_name=event.event_name,
                        event_detail=event.detail or None,
                    )

        event_task = asyncio.create_task(_consume_events())
        try:
            result = await micro_agent.execute(
                run_label="Process Email",
                task="",  # 邮件通过 signal 进入，不再通过 task
                session_manager=self.session_manager,
                session=session,
            )
        except asyncio.CancelledError:
            if self._is_stopping:
                self.logger.info(f"🛑 Session {session_id[:8]} 被 stop() 中断")
                await self._log_session_event(
                    session_id=session_id,
                    event_type="session",
                    event_name="user_interrupt",
                )
                if session.get("history"):
                    history = session["history"]
                    if history:
                        last = history[-1]
                        if last.get("role") == "assistant":
                            last["content"] = (
                                last.get("content", "").strip()
                                + "\n\n**执行中，用户要求中止**"
                            )
                        else:
                            history.append(
                                {"role": "assistant", "content": "**执行中，用户要求中止**"}
                            )
                try:
                    await self.session_manager.save_session(session)
                except Exception as e:
                    self.logger.warning(f"Failed to save session on stop: {e}")
                self._is_stopping = False
            else:
                raise
        except Exception as e:
            self.logger.error(f"❌ Session {session_id[:8]} 出错: {e}")
            user_name = self.runtime.get_user_agent_name() if self.runtime else "User"
            try:
                await micro_agent.send_internal_mail(
                    to=user_name,
                    subject=f"⚠️ {self.name} 执行出错",
                    body=f"在处理您的邮件时发生错误：\n\n{str(e)}\n\n请检查后回复「继续」以便继续执行。",
                )
            except Exception as e2:
                self.logger.error(f"发送错误通知邮件失败: {e2}")
        finally:
            event_task.cancel()
            try:
                await event_task
            except asyncio.CancelledError:
                pass
            await self._deactivate_session(session)

    async def _deactivate_session(self, session: dict):
        """
        停用 session：保存 session，清理 active 状态，处理下一个 waiting email。
        """
        session_id = session.get("session_id", "unknown")

        # 保存 session
        session["last_sender"] = self.name
        try:
            await self.session_manager.save_session(session)
        except Exception as e:
            self.logger.warning(f"Failed to save session on deactivate: {e}")

        # 不再断开 container shell — 保持空闲 shell 开销极低（~5MB 内存，0 CPU），
        # 且允许用户在 Agent 空闲时通过 Collab Terminal 持续操作。
        # 若 shell 意外断开，terminal/exec 端点会 lazy-recreate。

        # 清理 active 状态
        self._last_deactivated_session_id = session_id
        self.active_session_id = None
        self.active_micro_agent = None
        self._session_task = None
        self._execute_task = None
        if not self._is_stopping:
            self.current_user_session_id = None
            self.update_status(new_status=AgentStatus.IDLE)

        self.logger.info(f"✅ Session {session_id[:8]} 已停用")

        # 📝 写入 session event: session.deactivated
        await self._log_session_event(
            session_id=session_id,
            event_type="session",
            event_name="deactivated",
            event_detail={"reason": "normal"},
        )

        # 自动处理 waiting emails
        if self.waiting_emails:
            next_email = self.waiting_emails.pop(0)
            self.logger.info(f"📬 处理下一个 waiting email")
            try:
                await self._route_email(next_email)
            except Exception as e:
                self.logger.exception(f"Error routing waiting email: {e}")

    async def _history_worker(self):
        """
        历史整理 Worker（已暂停，等待后续改造）
        """
        try:
            while True:
                await asyncio.sleep(2)
                continue
        except asyncio.CancelledError:
            self.logger.info("🛑 History worker 已停止")
            raise

    # ==================== 🆕 双 Worker 模型结束 ====================

    def deprecated_resolve_real_path(self, filename: str) -> Path:
        """
        解析文件名并返回真实的绝对路径

        Args:
            filename: 可能是绝对路径、相对路径或单个文件名

        Returns:
            解析后的绝对路径

        Raises:
            FileNotFoundError: 文件未找到
            ValueError: 路径超出 workspace 范围
        """
        from pathlib import Path

        if self.runtime is None:
            raise RuntimeError("runtime 未注入，无法解析路径")

        # 转换为 Path 对象
        input_path = Path(filename)

        # 获取 workspace 路径
        workspace_root = self.runtime.paths.workspace_dir.resolve()

        # 情况1: 处理绝对路径
        if input_path.is_absolute():
            try:
                # 检查是否在 workspace 范围内
                resolved_path = input_path.resolve()

                # 检查路径是否在 workspace 下
                if not str(resolved_path).startswith(str(workspace_root)):
                    raise ValueError(f"Path {filename} is outside workspace")

                # 检查文件是否存在
                if not resolved_path.exists():
                    raise FileNotFoundError(f"File not found: {filename}")

                return resolved_path

            except Exception as e:
                raise ValueError(f"Invalid absolute path: {filename}") from e

        # 情况2: 处理相对路径
        # 判断是否是单个文件名（不包含路径分隔符）
        is_single_filename = "/" not in str(input_path) and "\\" not in str(input_path)

        # 定义搜索顺序的函数
        def try_resolve_in_workspace(workspace: Path) -> Optional[Path]:
            """在指定工作区中解析路径"""
            if not workspace:
                return None

            try:
                # 对于单个文件名，需要递归搜索
                if is_single_filename:
                    # 在工作区中递归搜索文件
                    for found_file in workspace.rglob(filename):
                        if found_file.is_file():
                            return found_file.resolve()
                else:
                    # 对于带路径的相对路径，直接解析
                    candidate = (workspace / input_path).resolve()
                    if candidate.exists() and candidate.is_file():
                        return candidate

            except Exception:
                pass

            return None

        # 按优先级顺序尝试解析
        # 1. 先尝试共享工作区
        resolved = try_resolve_in_workspace(self.current_workspace)
        if resolved:
            return resolved

        # 2. 再尝试私有工作区
        resolved = try_resolve_in_workspace(self.private_workspace)
        if resolved:
            return resolved

        # 3. 如果都没找到，抛出异常
        raise FileNotFoundError(f"File not found in any workspace: {filename}")

    def preview_system_prompt(
        self,
        yellow_pages: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
    ) -> str:
        """
        预览 System Prompt（不执行任务）

        用于调试或查看 Agent 配置后的完整 prompt，
        不需要实际运行任务就能看到 prompt 长什么样。

        Args:
            yellow_pages: 黄页信息（其他 Agent 列表）。
                如果为 None，使用默认空字符串。
            available_skills: 可用的 skill 列表。
                如果为 None，使用 profile 中的 skills 配置。

        Returns:
            str: 完整的 system prompt 文本

        Example:
            >>> agent = get_agent("alice")
            >>> prompt = agent.preview_system_prompt()
            >>> print(prompt)
        """
        # 准备 available_skills
        if available_skills is None:
            available_skills = self.profile.get("skills", [])

        for required in ["base", "email"]:
            if required not in available_skills:
                available_skills = [required] + available_skills

        # 预组装 system prompt 模板
        template_key = "COLLAB_MODE" if getattr(self, "collab_mode", False) else "SYSTEM_PROMPT"
        template_str = self.render_template(
            self.get_prompt_template(template_key),
            user_name=self.runtime.user_agent_name,
            agent_name=self.name,
            yellow_pages_section=yellow_pages or "",
        )

        # 加载 md skills
        md_skills = self._load_md_skills()

        # 创建临时 MicroAgent
        temp_micro = MicroAgent(
            parent=self, name=self.name, available_skills=available_skills,
            system_prompt=template_str, md_skills=md_skills,
        )

        # 渲染 prompt（注入 core_prompt）
        temp_micro._build_system_prompt()

        return temp_micro.system_prompt

    # ==========================================
    # 通用 Actions
    # ==========================================
