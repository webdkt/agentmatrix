import asyncio
import re
from typing import Dict, Optional, Callable, List, Any, Tuple, Union
from dataclasses import dataclass, asdict, field
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action

from .session_manager import SessionManager, AgentSessionStore
import traceback
import inspect
import json
import textwrap
import logging
from pathlib import Path
from ..core.basic_agent import BasicAgent
from ..core.micro_agent import MicroAgent
from ..core.signals import CoreEvent


# Agent 状态常量
class AgentStatus:
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"

    RECOVERING = "RECOVERING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"



class BaseAgent(BasicAgent):
    _log_from_attr = "name"  # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG

    def __init__(self, profile, profile_path: str = None):
        from ..core.skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.add_search_path("agentmatrix.desktop.skills")

        # BasicAgent 初始化：name, profile, profile_path, input_queue,
        # session state, brain, cerebellum, session_manager, skills, state_manager
        super().__init__(profile, profile_path)

        # inbox 向后兼容别名
        self.inbox = self.input_queue

        self.description = profile["description"]

        # persona 直接是字符串
        self.persona = profile.get("persona", "")

        # 加载其他 prompts（如 task_prompt）
        self.other_prompts = profile.get("prompts", {})

        # Prompt 模板缓存
        self._prompt_cache = {}

        self.backend_model = profile.get("backend_model", "default_llm")

        self.vision_brain = None  # 视觉大模型（支持图片理解的LLM）

        self._status = AgentStatus.IDLE
        from datetime import datetime

        self._status_since = datetime.now()

        # 状态历史（最近 10 条，用于前端查询）
        self.status_history = []
        self._max_status_history = 10

        self.last_received_email = None
        self.post_office = None

        # 事件回调 (Server 注入)
        self.async_event_callback: Optional[Callable] = None

        # Runtime 引用 (由 AgentMatrix 注入)
        self._runtime = None

        # action_registry 代替 actions_map
        self.action_registry = {}
        self.actions_meta = {}

        self.current_task_id = None
        self.current_user_session_id = None

        # 广播消息的回调（由 runtime 注入）
        self._broadcast_message_callback = None

        # 扫描 BaseAgent 自身的 actions（不包含 skills）
        self._scan_all_actions()


        # 双 Worker 模型（history_worker）
        self.pending_summaries_queue = []
        self.history_worker_task = None

        # Container Session（延迟初始化）
        self.container_session = None
        self.local_session = None

        # Whiteboard Manager（白板持久化 + 协同编辑）
        from .whiteboard_manager import WhiteboardManager
        self.whiteboard_manager = WhiteboardManager(self)

        # Todo Manager（任务清单持久化）
        from .todo_manager import TodoManager
        self.todo_manager = TodoManager(self)

        # 浏览器适配器（懒启动，Agent 级共享资源）
        self._browser_adapter = None

        # Collab Mode（运行时状态，不持久化）
        self.collab_mode: bool = False
        self._collab_output_loop: Optional[asyncio.AbstractEventLoop] = None
        self.current_collab_file: Optional[str] = None
        self._last_deactivated_session_id: Optional[str] = None

        # 记录最后一次 top-level MicroAgent 执行的 system prompt
        self.last_system_prompt = None

        self.logger.info(f"Agent {self.name} 初始化完成")

    def _init_container_session(self):
        """根据 session_type 配置初始化对应的 Session"""
        session_type = self.profile.get("session_type", "local")
        if session_type == "local":
            self._init_local_session()
        elif session_type == "container":
            self._init_container_session_impl()
        else:
            raise ValueError(f"Unknown session_type: '{session_type}'")

    def _init_local_session(self):
        """初始化本地持久 bash 会话（直接在宿主机执行）"""
        from .container.local_session import LocalSession

        home_dir = str(self.runtime.paths.get_agent_home_dir(self.name))
        env_bin = self.runtime.paths.get_shared_env_bin()

        session = LocalSession(
            home_dir=home_dir,
            logger=logging.getLogger(f"local_session.{self.name}"),
            env_bin_path=env_bin,
        )
        session.start()

        self.container_session = session
        self.local_session = session
        self.logger.info(f"Local Session 初始化成功 (HOME={home_dir})")

        self._setup_output_mirror()

    def _init_container_session_impl(self):
        """初始化容器内 Session（通过 Docker/Podman exec）"""
        if (
            not hasattr(self.runtime, "container_manager")
            or not self.runtime.container_manager
        ):
            raise RuntimeError(
                f"Agent '{self.name}' 配置为 session_type='container'，"
                "但容器运行时不可用。请安装 Docker/Podman，或将 session_type 改为 local。"
            )

        cm = self.runtime.container_manager
        cm.ensure_user(self.name)

        self.container_session = cm.get_container_session(self.name)
        self.local_session = None
        self.logger.info(
            f"Container Session 初始化成功 (session_id: {self.container_session.session_id})"
        )

        self._setup_output_mirror()

    async def switch_workspace(self, task_id: str) -> bool:
        """切换工作目录（根据 session 类型选择路径策略）"""
        if self.container_session is None:
            raise RuntimeError("Session 未初始化")

        # 1. 在宿主机创建目录（两种模式都需要）
        task_dir = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        # 2. 根据 session 类型选择 symlink 策略
        from .container.local_session import LocalSession
        if isinstance(self.container_session, LocalSession):
            # Local: 宿主机直接建 symlink
            home_dir = self.runtime.paths.get_agent_home_dir(self.name)
            symlink_path = home_dir / "current_task"
            if symlink_path.is_symlink() or symlink_path.exists():
                symlink_path.unlink()
            symlink_path.symlink_to(str(task_dir))
            exit_code, stdout, stderr = await asyncio.to_thread(
                self.container_session.execute, "cd ~/current_task && pwd"
            )
        else:
            # Container: 容器内建 symlink
            symlink_target = f"/data/agents/{self.name}/work_files/{task_id}"
            cmd = f"rm -f ~/current_task && ln -s {symlink_target} ~/current_task && cd ~/current_task && readlink -f ~/current_task"
            exit_code, stdout, stderr = await asyncio.to_thread(
                self.container_session.execute, cmd
            )

        if exit_code != 0:
            self.logger.warning(f"switch_workspace 失败: stderr={stderr}")
            return False

        self.logger.info(f"工作目录已切换: {self.name} -> {task_id}")
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
    ) -> str:
        """从对话历史生成 Working Notes（AgentShell 接口实现）。

        使用液态金属架构（Liquid Metal）：不固定结构，让 LLM 根据对话场景动态生成 Headers。

        Args:
            messages: 当前对话历史
            focus_hint: 可选，指导 LLM 重点关注某方面
        """
        from ..core.utils.parser_utils import working_notes_parser
        from ..core.utils.token_utils import format_session_messages

        # 注入 Agent Persona（如有）
        persona_hint = ""
        if self.persona:
            persona_hint = f"""

[Agent Persona Reference]
{self.persona[:100]}...

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

        step_3 = """## Step 3: 状态提取 (State Extraction)
- **去噪**：剔除客套话、重复信息。
- **消歧**：将代词（他/它/那个）还原为实体全名。
- **客观**：只记录事实和结论，不记录流水账。
- **完整**：保留关键内容和结果，原始目的中不可缺失的部分，后续行动必须持有的线索。
- **自包含**：Working Notes 是压缩后唯一的上下文来源，必须包含原始任务目标和所有必要的背景信息。"""

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

{step_3}

# Output Format (CRITICAL)
你必须用 <working_note> 和 </working_note> 标签包裹你的 Working Notes 输出。

格式如下：
<working_note>
你的 Markdown 格式的工作笔记内容
</working_note>

标签之外的所有内容都会被忽略。不要在标签外写任何解释、寒暄或确认语。整个回复只包含标签包裹的内容。

# Content Requirements
1. 内容必须是 Markdown 格式
2. 二级标题由你根据场景动态决定
3. 必须包含一个通用的 `## 🧠 关键上下文` 区域，用于兜底非结构化信息
4. 保持简洁：丢弃过时细节、冗余信息、探索过程性信息
5. 自包含：如果这是唯一的上下文，下一轮能否立刻接着干？其他人仅仅依靠此 Working Notes 就能理解当前状态、目标、所需的关键文件和下一步行动。

{persona_hint}
---
# Session History
{format_session_messages(messages)}
---
{focus_hint_block}

Start generating the Working Notes now. Remember: wrap your output in <working_note> tags.
"""

        working_notes = await self.brain.think_with_retry(
            initial_messages=prompt, parser=working_notes_parser, max_retries=3
        )

        return working_notes

    async def compress_messages(self, agent) -> None:
        """压缩 agent 的 messages（AgentShell 接口实现）。

        Desktop 实现：生成 working notes 替换全部对话历史。
        """
        # 生成 working notes
        working_notes = await self.generate_working_notes(
            agent.messages,
        )

        # 清理可能残留的标签（parser 已经提取了纯内容，但以防万一）
        if working_notes:
            working_notes = re.sub(r'<working_note>\s*', '', working_notes).strip()
            working_notes = re.sub(r'\s*</working_note>', '', working_notes).strip()
            working_notes = re.sub(r'\[WORKING NOTES\]\s*\n*', '', working_notes, count=1).strip()

        # 写入 session event
        session_id = self.current_session.get("session_id") if self.current_session else None
        if session_id:
            await self._log_session_event(session_id, "session", "message_auto_compress", {
                "step_count": agent.step_count,
                "working_notes_preview": working_notes if working_notes else None,
            })

        # 保留 system message
        has_system = agent.messages and agent.messages[0].get("role") == "system"

        # 构建新的 user message content（纯 working notes）
        new_user_content = f"[WORKING NOTES]\n{working_notes}\n\n请继续执行下一步。"

        # 重建 messages
        if has_system:
            agent.messages = [agent.messages[0], {"role": "user", "content": new_user_content}]
        else:
            agent.messages = [{"role": "user", "content": new_user_content}]

        # 保存到 session
        if self.current_session and self.session_manager:
            self.current_session["history"] = agent.messages
            await self.session_manager.save_session(self.current_session)

        # 重置变更计数器（不清空数据）
        self.whiteboard_manager.reset_change_counter()
        self.todo_manager.reset_change_counter()

    def is_llm_available(self) -> bool:
        """检查 LLM 服务是否可用。"""
        if not hasattr(self, "runtime") or self.runtime is None:
            return True
        monitor = self.runtime.llm_monitor
        if monitor is None:
            return True
        return monitor.llm_available.is_set()

    def notify_llm_unavailable(self) -> None:
        """通知 monitor LLM 服务不可用，触发恢复轮询。

        Lazy 模式下 monitor 不会主动发现故障，需要调用方在捕获到
        LLM 连接错误时主动调用此方法。
        """
        if not hasattr(self, "runtime") or self.runtime is None:
            return
        monitor = self.runtime.llm_monitor
        if monitor is None:
            return
        monitor.mark_unavailable()

    async def wait_for_llm_recovery(self) -> None:
        """等待 LLM 服务恢复。"""
        monitor = self.runtime.llm_monitor if self.runtime else None
        if monitor is None:
            return
        self.logger.info("⏳ Waiting for LLM service recovery...")
        await monitor.llm_available.wait()
        self.logger.info("✅ LLM service recovered!")

    # ========== MD Skill 管理 ==========

    def _load_md_skill_names(self) -> List[str]:
        """扫描 Agent 的 SKILLS 目录，返回 skill 名字列表。"""
        try:
            skills_dir = self.runtime.paths.get_agent_skills_dir(self.name)
            if not skills_dir.exists():
                return []

            names = []
            for item in skills_dir.iterdir():
                if not item.is_dir():
                    continue
                # 查找 skill.md（不区分大小写）
                for file in item.iterdir():
                    if file.is_file() and file.name.upper() == "SKILL.MD":
                        names.append(item.name)
                        break
            return names

        except Exception as e:
            self.logger.warning(f"Failed to load md skill names: {e}")
            return []

    def get_md_skill_prompt(self, skill_names: List[str]) -> str:
        """获取 MD Skill 的 prompt 文本。

        Shell 实现：读取 SKILL.md、提取描述、组装 prompt。
        """
        if not skill_names:
            return ""

        skills_dir = self.runtime.paths.get_agent_skills_dir(self.name)

        lines = [
            "#### B. 扩展技能库 (Procedural Skills)",
            f"你有{len(skill_names)}个额外扩展技能存放在 `~/SKILLS/` 目录。每个子目录对应一个技能，目录内包含 skill.md 描述文件。",
            "如果需要使用扩展技能，先列目录，看有什么技能（目录名代表了技能的名字）",
            "如果名字看上去可能是你需要的，就继续读里面的 skill.md 的开头，判断是否真的是你需要的技能",
            "如果是需要的技能，就继续阅读，理解如何使用。扩展技能的命令通常要通过 bash 执行",
            "",
            "可用扩展技能：",
        ]

        for name in skill_names:
            description = self._read_skill_description_from_dir(skills_dir / name)
            lines.append(f"- **{name}**: {description}")

        return "\n".join(lines)

    def _read_skill_description_from_dir(self, skill_dir: Path) -> str:
        """从 skill 目录中读取 SKILL.md 的 description。"""
        try:
            for file in skill_dir.iterdir():
                if file.is_file() and file.name.upper() == "SKILL.MD":
                    from ..core.utils import micro_agent_utils as _utils
                    return _utils.read_skill_description(file)
        except Exception:
            pass
        return "（请打开 skill 文件查看详细介绍）"

    @property
    def status(self):
        """只读属性：必须通过 update_status() 方法来修改"""
        return self._status

    # ========== StateManagerMixin hook ==========

    def _on_stop(self):
        """停止时取消当前 session 和 running actions。"""
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
            self.logger.info(f"Agent {self.name} 已停止当前 session")


    def get_status_snapshot(self) -> dict:
        """
        获取当前 Agent 的完整状态快照

        Returns:
            dict: Agent 完整状态
        """
        user_session_id = self.current_user_session_id
        if not user_session_id and self.current_task_id:
            user_session_id = self.current_task_id

        return {
            "status": self._status,
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

    # ---- UI Schema（前端控制结构树）----

    def get_ui_schema(self):
        """返回 UI action 的 schema 树，供前端渲染工具条/菜单。

        Override 在子类中扩展（调用 super().get_ui_schema() 并追加/插入节点）。

        目录节点: {"name": "...", "icon": "...", "children": [...]}
        Action 节点: {"action": "方法名", "icon": "...", "display_mode": "...", ...}
        """
        return [
            {
                "name": "control",
                "icon": "settings",
                "children": [
                    {"action": "pause_agent", "icon": "pause", "display_mode": "toast"},
                    {"action": "continue_agent", "icon": "play", "display_mode": "toast"},
                    {"action": "stop_agent", "icon": "square", "display_mode": "toast"},
                ]
            },
            {
                "name": "debug",
                "icon": "flask",
                "children": [
                    {"action": "view_current_prompt", "icon": "file-text", "display_mode": "markdown"},
                ]
            },
        ]

    @staticmethod
    def _find_action_in_schema(schema, action_name):
        """递归查找 schema 树中匹配 action_name 的叶子节点。"""
        for node in schema:
            if "children" in node:
                found = BaseAgent._find_action_in_schema(node["children"], action_name)
                if found:
                    return found
            elif node.get("action") == action_name:
                return node
        return None

    async def execute_ui_action(self, action_name: str, payload: dict = None) -> dict:
        """执行 UI action，将结果通过 UI_ACTION_RESULT 推送到前端弹窗展示（不写入 session event）。"""
        action_node = self._find_action_in_schema(self.get_ui_schema(), action_name)
        if not action_node:
            raise ValueError(f"UI action '{action_name}' not found")

        if action_node.get("requires_idle", False) and self._status != AgentStatus.IDLE:
            raise RuntimeError(f"Action '{action_name}' requires IDLE status")

        handler = getattr(self, action_name, None)
        if handler is None:
            raise RuntimeError(f"Handler '{action_name}' not found on {self.name}")

        # 只传 handler 接受的参数，过滤掉多余的（如 session_id）
        sig = inspect.signature(handler)
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            filtered_payload = payload or {}
        else:
            accepted = set(sig.parameters.keys()) - {"self"}
            filtered_payload = {k: v for k, v in (payload or {}).items() if k in accepted}

        result = handler(**filtered_payload)
        if asyncio.iscoroutine(result):
            result = await result

        serializable = result if isinstance(result, (str, int, float, bool, list, dict, type(None))) else str(result)

        # 直接广播 UI_ACTION_RESULT（不走 session event，不写入聊天时间线）
        if self._broadcast_message_callback:
            from datetime import datetime
            asyncio.create_task(self._broadcast_message_callback({
                "type": "UI_ACTION_RESULT",
                "agent_name": self.name,
                "data": {
                    "action_name": action_name,
                    "result": serializable,
                    "display_mode": action_node.get("display_mode", "text"),
                    "timestamp": datetime.now().isoformat(),
                },
            }))

        return {"result": serializable, "display_mode": action_node.get("display_mode", "text")}

    # ---- UI Action 方法（前端可调用）----

    async def pause_agent(self, session_id: str = ""):
        if self.active_session_id != session_id:
            return "Session mismatch"
        if self.is_paused:
            return "Already paused"
        await self.pause()
        return "Agent paused"

    async def continue_agent(self, session_id: str = ""):
        if self.is_paused:
            if self.active_session_id != session_id:
                return "Session mismatch"
            await self.resume()
            return "Agent resumed"
        if self._status == "STOPPED":
            if self.active_session_id != session_id:
                return "Session mismatch"
        if self._status in ("IDLE", "STOPPED"):
            from ..core.signals import TextSignal
            signal = TextSignal(text="continue", type_name="continue")
            signal.session_id = session_id
            await self._route_signal(signal)
            return "Continue signal sent"
        return "Nothing to continue"

    async def stop_agent(self, session_id: str = ""):
        if self.active_session_id != session_id:
            return "Session mismatch"
        self.stop()
        return "Agent stopped"

    async def view_current_prompt(self):
        """返回当前 system prompt，用于调试。"""
        if self.active_micro_agent and self.active_micro_agent.messages:
            msg = self.active_micro_agent.messages[0]
            if msg.get("role") == "system":
                return msg["content"]
        try:
            return self.preview_system_prompt()
        except Exception as e:
            return f"Error generating prompt: {e}"

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

    def resolve_path_to_host(self, file_path: str):
        """
        将容器内路径（~/xxx, /data/agents/xxx, 相对路径）转换为宿主机路径

        Args:
            file_path: 文件路径

        Returns:
            Path 或 None: 宿主机路径，无法转换时返回 None
        """
        if self.runtime is None:
            return None
        return self.runtime.paths.resolve_path_to_host(
            file_path, self.name, self.current_task_id
        )

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
        """Desktop 主循环：启动 BasicAgent.run() + history_worker。"""
        self.history_worker_task = asyncio.create_task(self._history_worker())

        await self.emit("SYSTEM", f"{self.name} Started")

        try:
            await super().run()
        except asyncio.CancelledError:
            if self.history_worker_task:
                self.history_worker_task.cancel()
                try:
                    await self.history_worker_task
                except (asyncio.CancelledError, Exception):
                    pass
            raise

    async def _main_loop(self):
        """
        Desktop: input_queue 消费 → _route_signal。

        input_queue 中的 item 都是 Signal（Email、BrowserSignal 等）。
        """
        self.logger.info("Desktop main loop 已启动")

        try:
            while True:
                await self.checkpoint()
                signal = await self.input_queue.get()

                try:
                    if isinstance(signal, Email):
                        self.last_received_email = signal

                    await self._route_signal(signal)

                    # 更新 per-participant reply tracker
                    if isinstance(signal, Email) and self.current_session is not None:
                        tracker = self.current_session.setdefault("reply_tracker", {})
                        tracker[signal.sender] = {
                            "last_email_id": signal.id,
                            "sender_session_id": signal.sender_session_id,
                            "replied": False,
                        }
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.exception(f"Error routing signal in {self.name}")
                finally:
                    self.input_queue.task_done()

        except asyncio.CancelledError:
            # 取消 session task
            if self._session_task and not self._session_task.done():
                if self.active_micro_agent:
                    for aid, info in self.active_micro_agent._running_actions.items():
                        task = info["task"] if isinstance(info, dict) else info
                        task.cancel()
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            self.logger.info("Desktop main loop 已停止")
            raise

    # ==========================================
    # BasicAgent override: 信号路由
    # ==========================================

    async def _resolve_session(self, signal) -> dict:
        """Desktop: 根据 signal 类型解析 session，记录事件。"""
        # 如果已经被解析过（从 waiting_signals 取出），直接返回
        if getattr(signal, '_desktop_resolved', False):
            return signal._resolved_session

        if isinstance(signal, Email):
            return await self._resolve_email_session(signal)
        else:
            return await super()._resolve_session(signal)

    async def _resolve_email_session(self, email: Email) -> dict:
        """Email signal → 从邮件元数据解析 session。"""
        session = await self.session_manager.get_session(email)
        session_id = session["session_id"]

        # 更新 recipient_session_id
        if email.recipient_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                recipient_session_id=session_id,
                receiver_name=self.name,
            )

        # 写入 session event: email.received
        body_preview = email.body or ""
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

        # 标记已解析（避免 waiting_signals 重路由时重复处理）
        email._desktop_resolved = True
        email._resolved_session = session

        return session

    async def _on_activate_session(self, session: dict, first_signal=None):
        """Desktop: session 激活后的 hook — workspace 切换、状态更新。"""
        session_id = session["session_id"]
        self.current_task_id = session["task_id"]

        # 只在真正切换到不同 session 时才清空 collab file
        if self._last_deactivated_session_id != session_id:
            self.current_collab_file = None

        # 设置 current_user_session_id（从首条信号提取）
        if first_signal:
            if isinstance(first_signal, Email) and self.runtime and first_signal.sender == self.runtime.get_user_agent_name():
                self.current_user_session_id = first_signal.sender_session_id
            else:
                self.current_user_session_id = None

        # 切换工作区
        if self.container_session is None:
            raise RuntimeError("Container Session 未初始化。")
        if not self.container_session.is_alive():
            self.logger.info(f"重建 container shell: {self.container_session.session_id}")
            try:
                self.container_session.start()
            except Exception as e:
                self.logger.error(f"重建 container shell 失败: {e}")
                raise RuntimeError(f"Container Session 启动失败: {e}")
        success = await self.switch_workspace(session["task_id"])
        if not success:
            self.logger.error(f"工作区切换失败: task_id={session['task_id']}")
            raise RuntimeError(f"工作区切换失败: {session['task_id']}")

        # 设置 whiteboard 文件路径
        wb_dir = self.private_workspace / ".matrix"
        wb_dir.mkdir(parents=True, exist_ok=True)
        self.whiteboard_manager.set_file_path(wb_dir / "whiteboard.json")
        self.todo_manager.set_file_path(wb_dir / "todo.json")

        # 写入 session event: session.activated
        await self._log_session_event(
            session_id=session_id,
            event_type="session",
            event_name="activated",
            event_detail={"task_id": session.get("task_id"), "original_sender": session.get("original_sender")},
        )

    async def _on_deactivate_session(self, session: dict):
        """Desktop: session 停用前的 hook — 状态广播、event logging。"""
        session_id = session.get("session_id", "unknown")

        # 保存 session（设置 last_sender）
        session["last_sender"] = self.name
        try:
            await self.session_manager.save_session(session)
        except Exception as e:
            self.logger.warning(f"Failed to save session on deactivate: {e}")

        self._last_deactivated_session_id = session_id

        if not self._is_stopping:
            self.current_user_session_id = None
            self.update_status(new_status=AgentStatus.IDLE)

        self.logger.info(f"Session {session_id[:8]} deactivated (Desktop)")

        # 写入 session event: session.deactivated
        await self._log_session_event(
            session_id=session_id,
            event_type="session",
            event_name="deactivated",
            event_detail={"reason": "normal"},
        )

    def _create_micro_agent(self) -> MicroAgent:
        """Desktop: 带有 base/email skills + md skills + custom prompt 的 MicroAgent。"""
        available_skills = list(self.profile.get("skills", []))
        for required in ["base", "email", "basic_planning"]:
            if required not in available_skills:
                available_skills = [required] + available_skills

        template_key = "COLLAB_MODE" if getattr(self, "collab_mode", False) else "SYSTEM_PROMPT"
        template_str = self.render_template(
            self.get_prompt_template(template_key),
            user_name=self.runtime.user_agent_name,
            agent_name=self.name,
            yellow_pages_section=self.post_office.yellow_page_exclude_me(self.name) or "",
        )

        md_skill_names = self._load_md_skill_names()

        micro = MicroAgent(
            parent=self, name=self.name,
            available_skills=available_skills,
            system_prompt=template_str,
            md_skill_names=md_skill_names,
        )

        # 绑定退出前 hook
        micro._before_exit_hook = self._on_before_exit

        # 绑定 action 前 hook：自动将 for_label 引用的 todo 设为 working
        async def _before_action_hook(action_name: str, params: dict, action_label: str = ""):
            if not action_label:
                return
            m = re.match(r'^#?(\d+)', action_label)
            if not m:
                return
            index = m.group(1)
            if self.todo_manager.data.get(index):
                self.todo_manager.set_status_by_index(index, "working")
                self.todo_manager.update_first_user_message(micro)
                self.todo_manager.update_task_reminder(micro)

        micro._before_action_hook = _before_action_hook

        # 注册 system prompt 热刷新 + whiteboard/todo 管理 hook：每轮 think 前执行
        async def _before_think_hook():
            # 1. 同步 whiteboard 文件（用户协同编辑检测）
            self.whiteboard_manager.sync_from_file(micro)
            # 2. 更新第一条 user message 中的 whiteboard
            self.whiteboard_manager.update_first_user_message(micro)
            # 3. 同步 todo 文件
            self.todo_manager.sync_from_file(micro)
            # 4. 更新第一条 user message 中的 todo
            self.todo_manager.update_first_user_message(micro)
            # 5. 更新 task reminder（注入最后一条 user message）
            self.todo_manager.update_task_reminder(micro)
            # 6. 检查变更计数 → 触发压缩
            if self.whiteboard_manager.should_compress or self.todo_manager.should_compress:
                await self.compress_messages(micro)
                self.whiteboard_manager.reset_change_counter()
                self.todo_manager.reset_change_counter()
            # 7. 刷新 system prompt
            new_prompt = self._assemble_system_prompt(micro)
            micro.update_system_message(new_prompt)

        micro._before_think_hook = _before_think_hook

        return micro

    def _assemble_system_prompt(self, micro_agent: MicroAgent) -> str:
        """完整的 system prompt 拼装流水线，每轮 think 前调用。

        Shell 负责：渲染模板（身份、persona、yellow_pages 等变量）。
        MicroAgent 负责：注入 $core_prompt（action list，最后一道工序）。
        """
        template_key = "COLLAB_MODE" if getattr(self, "collab_mode", False) else "SYSTEM_PROMPT"
        template_str = self.render_template(
            self.get_prompt_template(template_key),
            user_name=self.runtime.user_agent_name,
            agent_name=self.name,
            yellow_pages_section=self.post_office.yellow_page_exclude_me(self.name) or "",
        )

        micro_agent.system_prompt = template_str
        return micro_agent._finalize_system_prompt()

    def _get_run_label(self, session: dict) -> str:
        """Desktop: execute() 的 run_label。"""
        return "Process Email"

    def _create_session_store(self, session: dict):
        """Desktop: AgentSessionStore 持久化。"""
        return AgentSessionStore(session, self.session_manager)

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """Desktop: 处理 CoreEvent — 状态更新、邮件标记、事件持久化。"""
        if event.event_type == "status":
            self.update_status(new_status=event.event_name.upper())

        elif event.event_type == "signal" and event.event_name == "processed":
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

        elif event.event_type == "think" and event.event_name == "brain":
            detail = event.detail or {}
            raw_reply = detail.get("raw_reply", "")
            has_actions = bool(re.search(r'<action_script[^>]*>', raw_reply))

            if has_actions:
                # Has action blocks → strip scripts, log remaining as thought
                display_text = self._strip_action_script(raw_reply)
                if display_text:
                    await self._log_session_event(
                        session_id=session_id,
                        event_type="think",
                        event_name="brain",
                        event_detail={
                            "step_count": detail.get("step_count"),
                            "thought": display_text,
                        },
                    )
            else:
                # No action blocks → chat message from the agent
                text = raw_reply.strip()
                if text:
                    msg_type = "question" if re.search(r'[?？❓？]\s*$', text) else "statement"
                    await self._log_session_event(
                        session_id=session_id,
                        event_type="chat-msg",
                        event_name="agent",
                        event_detail={
                            "step_count": detail.get("step_count"),
                            "text": text,
                            "msg_type": msg_type,
                        },
                    )

        elif event.event_type == "session" and event.event_name == "exit_msg":
            detail = event.detail or {}
            await self._log_session_event(
                session_id=session_id,
                event_type="session",
                event_name="exit_msg",
                event_detail={
                    "exit_msg_type": detail.get("exit_msg_type"),
                },
            )

        else:
            await self._log_session_event(
                session_id=session_id,
                event_type=event.event_type,
                event_name=event.event_name,
                event_detail=event.detail or None,
            )

    @staticmethod
    def _strip_action_script(text: str) -> str:
        """去掉 <action_script> 块，用于前端展示。"""
        return re.sub(r'<action_script[^>]*>.*?</action_script>', '', text, flags=re.DOTALL).strip()

    def _handle_session_cancelled(self, session: dict):
        """Desktop: session 被取消时的处理（stop 中断）。"""
        if not self._is_stopping:
            # 非 stop 的取消，重新抛出
            raise asyncio.CancelledError()

        session_id = session.get("session_id", "unknown")
        self.logger.info(f"Session {session_id[:8]} 被 stop() 中断")

        # 记录用户中断
        asyncio.create_task(self._log_session_event(
            session_id=session_id,
            event_type="session",
            event_name="user_interrupt",
        ))

        # 修改 session history
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
            asyncio.create_task(self.session_manager.save_session(session))
        except Exception as e:
            self.logger.warning(f"Failed to save session on stop: {e}")

        self._is_stopping = False
        self.current_user_session_id = None
        self._session_task = None
        self.active_session_id = None
        self.current_session = None
        self.update_status(new_status=AgentStatus.IDLE)

    async def _handle_session_error(
        self, micro_agent: MicroAgent, session: dict, error: Exception
    ):
        """Desktop: session 出错时发送通知邮件。"""
        session_id = session.get("session_id", "unknown")
        self.logger.error(f"Session {session_id[:8]} error: {error}")

        user_name = self.runtime.get_user_agent_name() if self.runtime else "User"
        try:
            await micro_agent.send_internal_mail(
                to=user_name,
                subject=f"⚠️ {self.name} 执行出错",
                body=f"在处理您的邮件时发生错误：\n\n{str(error)}\n\n请检查后回复「继续」以便继续执行。",
            )
        except Exception as e2:
            self.logger.error(f"发送错误通知邮件失败: {e2}")

    async def _on_execute_done(self, session: dict):
        """Desktop: execute 结束后更新状态为 IDLE。"""
        if not self._is_stopping:
            self.update_status(new_status=AgentStatus.IDLE)

    # reply reminder tag，用于包裹和清理历史中的提醒消息
    _REPLY_REMINDER_TAG = "system-auto-reply-reminder"

    async def _on_before_exit(self) -> bool:
        """MicroAgent _run_loop 退出前的 hook。返回 True 允许退出，False 阻止退出。"""
        import re
        from ..core.signals import TextSignal

        session = self.current_session
        if not session:
            return True

        tracker = session.get("reply_tracker", {})
        user_name = self.runtime.get_user_agent_name() if self.runtime else "User"
        unreplied = [
            (p, info) for p, info in tracker.items()
            if not info.get("replied", True) and p != user_name
        ]

        if not unreplied:
            return True  # 没有未回复，允许退出

        # 清理历史中已有的 reply-reminder 消息块
        self._purge_reply_reminders()

        names = "、".join(p for p, _ in unreplied)
        reminder_text = (
            f"你还没有回复 {names} 的邮件。"
            f"如需回复请使用 send_internal_mail，如无需回复请忽略本消息。"
        )
        wrapped = f"<{self._REPLY_REMINDER_TAG}>\n{reminder_text}\n</{self._REPLY_REMINDER_TAG}>"
        reminder = TextSignal(
            text=wrapped,
            type_name="reply_reminder",
        )
        # 先标记为已提醒，防止无限循环
        for _, info in unreplied:
            info["replied"] = True

        self.active_micro_agent.signal_queue.put_nowait(reminder)
        self.logger.info(f"Injected reply reminder for: {names}")
        return False  # 注入了信号，阻止退出，让 loop 继续

    def _purge_reply_reminders(self):
        """从 user messages 中移除所有 <system-auto-reply-reminder> 块。

        如果移除后 content 变空，设为 "continue"。
        """
        import re

        tag = self._REPLY_REMINDER_TAG
        pattern = re.compile(
            rf'\n*<{tag}>.*?</{tag}>\n*',
            re.DOTALL,
        )

        for msg in self.active_micro_agent.messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content")
            if isinstance(content, str):
                cleaned = pattern.sub('\n', content).strip()
                msg["content"] = cleaned if cleaned else "continue"
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        cleaned = pattern.sub('\n', item["text"]).strip()
                        item["text"] = cleaned if cleaned else "continue"

    # _run_session, _deactivate_session — 由 BasicAgent 提供

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

        for required in ["base", "email", "basic_planning"]:
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

        # 加载 md skill 名字列表
        md_skill_names = self._load_md_skill_names()

        # 创建临时 MicroAgent（用于获取 action_registry）
        temp_micro = MicroAgent(
            parent=self, name=self.name, available_skills=available_skills,
            system_prompt=template_str, md_skill_names=md_skill_names,
        )

        # MicroAgent 负责最后一道：注入 action list
        return temp_micro._finalize_system_prompt()

    # ==========================================
    # 通用 Actions
    # ==========================================
