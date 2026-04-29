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
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any, Union
import logging
import time
import json
import re
from .agent_shell import AgentShell


@dataclass
class Signal:
    type: str  # "email", "action_completed", "action_failed", "actions_completed"
    payload: Any


from .log_util import AutoLoggerMixin
from .exceptions import LLMServiceUnavailableError
from .action import register_action
from .message import Email
from .utils.token_utils import estimate_messages_tokens

from .agent_shell import AgentShell
from .utils import micro_agent_utils as _utils


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

    # persona 存储在 Shell (root_agent) 上，MicroAgent 通过 property 透明代理
    @property
    def persona(self) -> str:
        return self.root_agent.persona

    @persona.setter
    def persona(self, value: str):
        self.root_agent.persona = value

    def __init__(
        self,
        parent: Union["AgentShell", "MicroAgent"],
        name: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
        system_prompt: str = "",
        md_skills: Optional[Dict[str, str]] = None,
        compression_token_threshold: int = 64000,
    ):
        """
        初始化 Micro Agent

        Args:
            parent: 父级 Agent（BaseAgent 或 MicroAgent）
                - 自动继承 brain, cerebellum, action_registry, logger
            name: Agent 名称（可选，自动生成）
            available_skills: 可用技能列表（如 ["file", "browser"]）
            system_prompt: system prompt 模板（Shell 或创建者预组装）
            md_skills: 已加载的 md skill 字典 {name: description}
            compression_token_threshold: 触发消息压缩的 token 阈值（默认 64000）
        """
        # 基本信息（必须在动态组合之前设置，因为 _create_dynamic_class 需要 self.name）
        self.name = name or f"MicroAgent_{uuid.uuid4().hex[:8]}"
        self.parent = parent
        
        # 🆕 动态组合 Skill Mixins（新架构核心）
        if available_skills:
            self.__class__ = self._create_dynamic_class(available_skills)

        # ========== session_context ==========
        # ========== 从 parent 自动继承组件 ==========
        self.brain = parent.brain
        self.cerebellum = parent.cerebellum

        # ========== 🆕 扫描所有 actions（新架构 - 嵌套结构）==========
        # action_registry 结构：
        #     _by_skill: {skill_name: {action_name: method}}
        #     _flat: {action_name: method, "skill.action": method}
        #     _aliases: {action_name: "skill.action"}
        #     _metadata: {action_name: {skill_name, action_name, original_name}}
        self.action_registry = {
            "_by_skill": {},
            "_flat": {},
            "_aliases": {},
            "_metadata": {},  # 🆕 存储元数据（因为绑定方法无法设置属性）
        }
        self._scan_all_actions()

        # logger: 直接使用 parent 的 logger（不创建新日志文件）
        self._internal_logger = parent.logger  # 绕过 AutoLoggerMixin 的懒加载

        # ========== 找到根 Agent ==========
        

        if isinstance(parent, AgentShell):
            self.root_agent = parent
        else:
            self.root_agent = parent.root_agent

        # ========== 其他配置 ==========
        self.messages: List[Dict] = []  # 对话历史
        self.run_label: Optional[str] = None  # 执行标识
        self.last_action_name: Optional[str] = None  # 记录最后执行的 action 名字
        
        self.scratchpad: List[str] = []  # 草稿纸：工作过程中随手记录的要点，压缩时辅助生成 Working Notes
        self.scratchpad_limit: int = 8  # scratchpad 积累到此条数时触发自动压缩

        # ========== 压缩相关 ==========
        self.compression_token_threshold = compression_token_threshold
        # self.last_compression_step = 0  # 上次压缩时的步数

        # ========== system prompt（Shell 或创建者预组装的模板）==========
        self.system_prompt = system_prompt
        self.md_skills = md_skills or {}

        # ========== Skill 上下文 ==========
        # 供 skill 存取自己的属性，避免 mixin __init__ 的 MRO 问题
        # skill 按名字空间存取: self.skill_context.setdefault("skill_name", {})["key"] = value
        self.skill_context: dict = {}

        # ========== 信号驱动架构 ==========
        self.signal_queue: asyncio.Queue = asyncio.Queue()
        self._running_actions: Dict[str, dict] = {}  # {action_id: {"task": Task, "label": str}}
        self._action_counter: int = 0
        self._pending_processed_ids: List[str] = []
        self._no_action_reflected: bool = False  # 是否已经 reflect 过"无 action"的情况

        # 日志
        self.logger.info(
            f"MicroAgent '{self.name}' initialized (parent: {parent.name})"
        )

    

    def _create_dynamic_class(self, available_skills: List[str]) -> type:
        """
        动态创建包含 Skill Mixins 的类

        Args:
            available_skills: 技能名称列表（如 ["file", "browser", "git_workflow"]）

        Returns:
            type: 动态创建的类

        Example:
            available_skills = ["file", "browser"]
            返回：type('DynamicAgent_MicroAgent_abc123',
                     (MicroAgent, FileSkillMixin, BrowserSkillMixin),
                     {})
        """
        from .skills.registry import SKILL_REGISTRY

        # 使用统一的 get_skills() 接口（Lazy Load）
        result = SKILL_REGISTRY.get_skills(available_skills)
        mixin_classes = result.python_mixins

        # 检查加载失败的情况
        if result.failed_skills:
            self.logger.warning(f"  ⚠️  以下 Skills 加载失败: {result.failed_skills}")

        if not mixin_classes:
            self.logger.warning(f"  ⚠️  没有找到可用的 Skills: {available_skills}")
            return self.__class__

        # 记录 Python Mixins 日志
        for mixin in mixin_classes:
            self.logger.debug(f"  🧩 混入 Skill Mixin: {mixin.__name__}")

        # 动态创建类（Python 的 type 函数）
        # type(name, bases, dict)
        dynamic_class = type(
            f"DynamicAgent_{self.name}",  # 类名
            (self.__class__,) + tuple(mixin_classes),  # 继承链
            {},  # 额外的类属性
        )

        return dynamic_class

    _BASH_CANCEL_HINT = "\n\n注意：被取消的任务中可能包含 bash 命令，如果涉及网络请求/安装等长时间操作，命令可能仍在容器中运行，如需终止请使用 `ps` + `kill`。"

    @register_action(
        short_desc="取消正在执行的操作",
        description="取消当前正在运行的操作。如果有多个操作在同时运行，可以通过 action_id 指定取消哪个。",
        param_infos={"action_id": "要取消的 action ID（可选，不填则取消所有正在运行的操作）"},
    )
    async def cancel_action(self, action_id: str = None) -> str:
        """取消正在运行的 action tasks"""
        _SENTINEL = object()

        if action_id and action_id in self._running_actions:
            info = self._running_actions.pop(action_id, _SENTINEL)
            if info is _SENTINEL:
                return f"未找到 {action_id}"
            task = info["task"] if isinstance(info, dict) else info
            label = info.get("label", "") if isinstance(info, dict) else ""
            action_names = info.get("action_names", []) if isinstance(info, dict) else []
            display_name = f"{action_id.rsplit('_', 1)[0]}: {label}" if label else action_id
            task.cancel()
            result = f"已取消 [{display_name}]"
            if "bash" in action_names:
                result += self._BASH_CANCEL_HINT
            return result
        elif self._running_actions:
            # pop 所有 entries（除了自己），这样被取消 action 的 callback 触发时会跳过信号
            # 保留自己的 entry，让 callback 能正确 put cancel 结果信号
            current = asyncio.current_task()
            entries = {}
            to_keep = {}
            for aid, info in self._running_actions.items():
                task = info["task"] if isinstance(info, dict) else info
                if task is current:
                    to_keep[aid] = info
                else:
                    entries[aid] = info
            self._running_actions.clear()
            self._running_actions.update(to_keep)
            cancelled = []
            has_bash = False
            for aid, info in entries.items():
                task = info["task"] if isinstance(info, dict) else info
                label = info.get("label", "") if isinstance(info, dict) else ""
                action_names = info.get("action_names", []) if isinstance(info, dict) else []
                if "bash" in action_names:
                    has_bash = True
                action_name = aid.rsplit("_", 1)[0]
                display_name = f"{action_name}: {label}" if label else action_name
                cancelled.append(display_name)
                task.cancel()
            names = ", ".join(cancelled)
            result = f"已取消 {len(cancelled)} 个操作: [{names}]"
            if has_bash:
                result += self._BASH_CANCEL_HINT
            return result
        else:
            return "当前没有正在运行的操作"

    def _build_no_action_reflect_message(self, action_section_text: str, raw_reply: str = "") -> Optional[str]:
        return _utils.build_no_action_reflect_message(action_section_text, raw_reply, self.action_registry["_flat"])

    def _build_exit_verification_prompt(self, raw_reply: str) -> str:
        return _utils.build_exit_verification_prompt(raw_reply)

    def _signal_text(self, signal, compress=False) -> str:
        """单个 signal 的纯文本生成（无副作用）"""
        if signal.type == "email":
            batch = signal.payload
            text = f"[新邮件] 来自 {batch['sender']}: {batch['subject']}\n{batch['body']}"
            attachments = batch.get("attachments", [])
            if attachments:
                text += "\n" + "\n".join(
                    f"附件已保存在 {att.get('container_path', att.get('filename', ''))}"
                    for att in attachments
                )
            return text
        elif signal.type in ["action_completed", "actions_completed"]:
            return self._format_combined_results(
                signal.payload.get("results", []), compress=compress
            )
        elif signal.type == "no_action_reflect":
            return signal.payload["message"]
        elif signal.type == "action_continue":  # 🆕 新增：验证后继续执行
            return signal.payload["message"]
        return ""

    def _signals_text(self, signals, compress=False) -> str:
        """批量 signal 的文本拼接"""
        return "\n\n".join(self._signal_text(sig, compress=compress) for sig in signals)

    async def inject_signals(self, signals):
        """Pre-think: 生成完整文本并注入 messages"""
        if not signals:
            return

        for signal in signals:
            self.logger.info(f"Injecting signal: {signal.type}")
            signal_detail = {"signal_type": signal.type}
            if signal.type == "email":
                signal_detail["email_ids"] = signal.payload.get("email_ids", [])
                signal_detail["sender"] = signal.payload.get("sender")
            elif signal.type in ["action_completed", "actions_completed"]:
                results = signal.payload.get("results", [])
                signal_detail["result_count"] = len(results)
                signal_detail["action_names"] = [r.get("action_name", "") for r in results]
            await self._log_event("session", "processing_signal", signal_detail)

        text = self._signals_text(signals)

        if self._running_actions:
            running = ", ".join(aid.rsplit("_", 1)[0] for aid in self._running_actions)
            text += f"\n\n**Action {running} Still Running**"

        self._add_message("user", text)

        for sig in signals:
            if sig.type == "email":
                self._pending_processed_ids.extend(sig.payload.get("email_ids", []))


    def _on_batch_done(self, action_id, task):
        """batch task 完成后的回调 - 发送原始 results 数组"""
        info = self._running_actions.pop(action_id, None)
        if info is None:
            return
        try:
            results = task.result()  # 获取 results 数组
            self.signal_queue.put_nowait(Signal(
                type="actions_completed",
                payload={"results": results}
            ))
        except Exception as e:
            self.signal_queue.put_nowait(Signal(
                type="actions_completed",
                payload={"results": [{"action_name": "batch", "label": "", "error": str(e), "status": "error"}]}
            ))

    @register_action(
        short_desc="查看skill或action帮助[skill?, action?], ",
        description="查看 skill 或 action 的详细使用信息",
        param_infos={
            "target": "目标，格式：skill_name、action_name 或 skill_name.action_name（可选）"
        },
    )
    async def help(self, target: str = None) -> str:
        """
        查询帮助信息

        用法：
        - help() → 列出所有 skills
        - help("file") → 显示 skill 的所有 actions
        - help("read") → 显示 action 的详细参数（自动查找）
        - help("file.read") → 显示 action 的详细参数（指定 skill）

        Args:
            target: 目标，支持 skill_name、action_name 或 skill_name.action_name 格式

        Returns:
            帮助信息文本
        """
        if not target:
            # 列出所有 skills
            lines = ["=== 可用的 Skills ===\n"]

            for skill_name, actions in self.action_registry["_by_skill"].items():
                skill_desc = self._get_skill_description(skill_name)
                action_names = list(actions.keys())

                lines.append(f"**{skill_name}**")
                if skill_desc:
                    lines.append(f"  {skill_desc}")
                lines.append(f"  可用 actions: {', '.join(action_names)}")
                lines.append("")

            lines.append(
                '使用 help("xxx") 查看技能或动作，help("xxx.yyy") 查看指定动作'
            )
            return "\n".join(lines)

        # 解析 target
        parts = target.split(".")

        if len(parts) == 1:
            # 可能是 skill_name 或 action_name
            candidate = parts[0]

            # 先检查是否是 skill
            if candidate in self.action_registry["_by_skill"]:
                # 显示 skill 的所有 actions
                skill_desc = self._get_skill_description(candidate)
                actions = self.action_registry["_by_skill"][candidate]

                lines = [f"=== {candidate.capitalize()} Skill ===\n"]

                if skill_desc:
                    lines.append(f"{skill_desc}\n")

                lines.append("可用 actions:\n")

                for action_name, method in actions.items():
                    desc = getattr(method, "_action_desc", "No description")
                    params = getattr(method, "_action_param_infos", {})

                    lines.append(f"- **{action_name}**: {desc}")

                    if params:
                        param_list = ", ".join(params.keys())
                        lines.append(f"  参数: {param_list}")
                    else:
                        lines.append(f"  无参数")

                    lines.append("")

                return "\n".join(lines)

            # 检查是否是 action（在 _flat 中查找）
            elif candidate in self.action_registry["_flat"]:
                # 查找 action 所属的 skill
                for skill_name, actions in self.action_registry["_by_skill"].items():
                    if candidate in actions:
                        method = actions[candidate]
                        desc = getattr(method, "_action_desc", "No description")
                        params = getattr(method, "_action_param_infos", {})

                        lines = [
                            f"=== {skill_name}.{candidate} ===\n",
                            f"描述: {desc}\n",
                            f"参数:\n",
                        ]

                        if params:
                            for param_name, param_desc in params.items():
                                lines.append(f"- **{param_name}**: {param_desc}")
                        else:
                            lines.append("(无参数)")

                        return "\n".join(lines)

                return f"❌ Action '{candidate}' 找不到所属 skill"

            else:
                return f"❌ '{candidate}' 既不是 skill 也不是 action"

        elif len(parts) == 2:
            # help("file.read") → 显示 action 的详细参数
            skill_name, action_name = parts

            if skill_name not in self.action_registry["_by_skill"]:
                return f"❌ Skill '{skill_name}' 不存在"

            if action_name not in self.action_registry["_by_skill"][skill_name]:
                return f"❌ Action '{action_name}' 在 skill '{skill_name}' 中不存在"

            method = self.action_registry["_by_skill"][skill_name][action_name]
            desc = getattr(method, "_action_desc", "No description")
            params = getattr(method, "_action_param_infos", {})

            lines = [
                f"=== {skill_name}.{action_name} ===\n",
                f"描述: {desc}\n",
                f"参数:\n",
            ]

            if params:
                for param_name, param_desc in params.items():
                    lines.append(f"- **{param_name}**: {param_desc}")
            else:
                lines.append("(无参数)")

            return "\n".join(lines)

        else:
            return f'❌ 格式错误。使用 help()、help("skill")、help("action") 或 help("skill.action")'

    def _scan_all_actions(self):
        """
        扫描自身（包括继承链）的所有 @register_action 方法

        新架构：
        1. 按 skill 分组存储（_by_skill）
        2. 自动检测并重命名冲突的 action
        3. 填充 _flat（快速查找）和 _aliases（解析映射）
        """
        import inspect

        # 已注册的 action 名称（用于冲突检测）
        registered_actions = set()

        # 已注册的 skill 名称（用于统计）
        registered_skills = set()

        # 遍历 self 的类及其所有父类（MRO - Method Resolution Order）
        for cls in self.__class__.__mro__:
            # 🔥 过滤逻辑：
            # 1. 扫描所有 *SkillMixin 类（真正的 skills）
            # 2. 扫描 MicroAgent 类本身（获取 help 等内置 actions）
            # 3. 排除动态类（DynamicAgent_*）和其他类
            is_skill_mixin = cls.__name__.endswith("SkillMixin")
            is_microagent_class = cls.__name__ == "MicroAgent"

            if not (is_skill_mixin or is_microagent_class):
                continue

            # 特殊处理：MicroAgent 的 actions 归入 base skill
            if is_microagent_class:
                skill_name = "base"
            else:
                # 🔥 推断 skill 名称
                skill_name = self._infer_skill_name(cls.__name__)

            registered_skills.add(skill_name)

            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, "_is_action") and method._is_action:
                    # 🔥 检测冲突
                    if name in registered_actions:
                        # 冲突！自动重命名
                        new_name = f"{skill_name}_{name}"

                        self.logger.info(
                            f"  🔀 Action name conflict: '{name}' in {cls.__name__}. "
                            f"Auto-renamed to '{new_name}'"
                        )

                        # 创建新的绑定方法
                        bound_method = getattr(self, name)

                        # 在实例上设置新方法
                        setattr(self, new_name, bound_method)

                        # 注册到 _by_skill
                        if skill_name not in self.action_registry["_by_skill"]:
                            self.action_registry["_by_skill"][skill_name] = {}
                        self.action_registry["_by_skill"][skill_name][new_name] = (
                            bound_method
                        )

                        # 注册到 _flat（完整命名）
                        self.action_registry["_flat"][f"{skill_name}.{name}"] = (
                            bound_method
                        )
                        self.action_registry["_flat"][new_name] = bound_method

                        # 记录别名映射
                        self.action_registry["_aliases"][name] = f"{skill_name}.{name}"

                        self.logger.debug(
                            f"  ✅ 注册 Action: {new_name} (来自 {cls.__name__}, 重命名)"
                        )

                    else:
                        # 无冲突，正常注册
                        bound_method = getattr(self, name)
                        # 🆕 在 _metadata 中记录元数据
                        self.action_registry["_metadata"][name] = {
                            "skill_name": skill_name,
                            "action_name": name,
                            "is_renamed": False,
                        }

                        # 注册到 _by_skill
                        if skill_name not in self.action_registry["_by_skill"]:
                            self.action_registry["_by_skill"][skill_name] = {}
                        self.action_registry["_by_skill"][skill_name][name] = (
                            bound_method
                        )

                        # 注册到 _flat（简写）
                        self.action_registry["_flat"][name] = bound_method

                        # 注册到 _flat（完整命名）
                        self.action_registry["_flat"][f"{skill_name}.{name}"] = (
                            bound_method
                        )

                        registered_actions.add(name)

                        self.logger.debug(
                            f"  ✅ 注册 Action: {name} (来自 {cls.__name__})"
                        )

        # 日志汇总
        total_actions = sum(
            len(actions) for actions in self.action_registry["_by_skill"].values()
        )
        self.logger.info(
            f"✅ 扫描完成: {len(registered_skills)} 个 skills, "
            f"{total_actions} 个 actions"
        )

    def _infer_skill_name(self, class_name: str) -> str:
        return _utils.infer_skill_name(class_name)

    def _resolve_action(self, action_call: str):
        """
        解析 action 调用（支持命名空间）

        支持：
        - "file.read" → 完整命名（明确指定）
        - "read" → 简写（自动解析，如果不冲突）

        Args:
            action_call: action 调用字符串

        Returns:
            bound_method: 绑定的方法

        Raises:
            ValueError: action 不存在或有歧义
        """
        # 格式1：完整命名 "skill.action"
        if "." in action_call:
            skill_name, action_name = action_call.split(".", 1)

            # 从 _by_skill 查找
            if skill_name in self.action_registry["_by_skill"]:
                if action_name in self.action_registry["_by_skill"][skill_name]:
                    return self.action_registry["_by_skill"][skill_name][action_name]

            # 如果 _by_skill 找不到，尝试 _flat
            full_name = f"{skill_name}.{action_name}"
            if full_name in self.action_registry["_flat"]:
                return self.action_registry["_flat"][full_name]

            raise ValueError(f"Action '{action_call}' not found")

        # 格式2：简写 "action"
        else:
            # 检查是否有歧义（多个 skill 有同名 action）
            matches = []
            for skill_name, actions in self.action_registry["_by_skill"].items():
                if action_call in actions:
                    matches.append(skill_name)

            if len(matches) == 1:
                # 唯一，返回
                return self.action_registry["_by_skill"][matches[0]][action_call]

            elif len(matches) > 1:
                # 歧义！
                raise ValueError(
                    f"Ambiguous action '{action_call}'. Found in {len(matches)} skills: {matches}. "
                    f"Please use 'skill.action' format."
                )

            else:
                # 尝试从 _flat 查找
                if action_call in self.action_registry["_flat"]:
                    return self.action_registry["_flat"][action_call]

                raise ValueError(f"Action '{action_call}' not found")



    # ==================== 🆕 自动压缩机制 ====================

    def _should_compress_messages(self) -> bool:
        """
        判断是否应该压缩 messages

        双通道触发：
        1. token 阈值（64K tokens）— 被动阈值
        2. scratchpad 积累量 — 主动信号，LLM 自己认为已产生足够多值得总结的信息

        Returns:
            bool: 是否应该压缩
        """
        total_tokens = estimate_messages_tokens(self.messages)
        if total_tokens >= self.compression_token_threshold:
            self.logger.info(f"📦 Messages 达到 {total_tokens} tokens，自动压缩...")
            return True
        if len(self.scratchpad) >= self.scratchpad_limit:
            self.logger.info(f"📝 Scratchpad 积累 {len(self.scratchpad)} 条，自动压缩...")
            return True
        return False

    async def _compress_messages(self) -> str:
        """
        压缩 messages，保留 system_prompt，添加总结

        新逻辑：
        1. 永远保留第一个 system message（如果有的话）
        2. Top-level MicroAgent: 使用邮件历史 + WORKING NOTES
        3. 嵌套 MicroAgent: 保留原始 user message + WORKING NOTES
        4. 结果：[system?, user(邮件历史/原始+working_notes)]

        Returns:
            str: 生成的 working_notes
        """
        # 压缩前：保存待总结 messages（仅 top-level）//这部分应该不要了
        
        #if self._is_top_level_microagent():
        #    self._push_pending_summary()

        working_notes = await self.root_agent.generate_working_notes(
            self.messages,
            scratchpad=self.scratchpad,
            is_top_level=self._is_top_level_microagent(),
        )

        # 剥掉 working_notes 开头可能带的 [WORKING NOTES]（LLM 从 session history 复读出来的）
        if working_notes and "[WORKING NOTES]" in working_notes:
            working_notes = re.sub(
                r'\[WORKING NOTES\]\s*\n*', '', working_notes, count=1
            ).strip()

        # 📝 写入 session event: session.message_auto_compress
        await self._log_event("session", "message_auto_compress", {
            "step_count": self.step_count,
            "working_notes_preview": working_notes if working_notes else None,
        })

        # ========== 1. 处理 system message ==========
        has_system = self.messages and self.messages[0].get("role") == "system"

        # ========== 2. 判断是否是 top-level MicroAgent ==========
        if self._is_top_level_microagent():
            # === Top-level MicroAgent 特殊逻辑：使用邮件历史 ===
            try:
                # 获取 session 所有邮件
                emails = await self.root_agent.post_office.get_emails_by_session(
                    session_id=self.session["session_id"],
                    agent_name=self.root_agent.name,
                )
                self.logger.debug(f"📧 已加载 {len(emails)} 封邮件")

                # 构建 Email History（聊天风格）
                email_history = self._format_email_history(emails)

                # 构建 user message: Email History + WORKING NOTES
                new_user_content = (
                    f"{email_history}\n\n[WORKING NOTES]\n{working_notes}"
                )
            except Exception as e:
                # 如果获取邮件失败，降级到原有逻辑
                self.logger.warning(f"⚠️ 获取邮件历史失败，降级到原有逻辑: {e}")
                # 找到第一个 user message 作为原始内容
                first_user_msg = None
                for msg in self.messages:
                    if msg.get("role") == "user":
                        first_user_msg = msg
                        break
                if first_user_msg:
                    original_content = first_user_msg.get("content", "")
                    new_user_content = (
                        f"{original_content}\n\n[WORKING NOTES]\n{working_notes}"
                    )
                else:
                    new_user_content = (
                        f"[WORKING NOTES]\n{working_notes}\n\n请继续执行下一步。"
                    )
        else:
            # === 嵌套 MicroAgent：保持现有逻辑 ===
            # 找到第一个 user message（原始用户请求）
            first_user_msg = None
            for msg in self.messages:
                if msg.get("role") == "user":
                    first_user_msg = msg
                    break

            if not first_user_msg:
                # 异常情况：没有 user message，创建一个新的
                new_user_content = (
                    f"[WORKING NOTES]\n{working_notes}\n\n请继续执行下一步。"
                )
            else:
                # 正常情况：处理第一个 user message
                original_content = first_user_msg.get("content", "")

                # 检查是否有旧 working notes
                if "[WORKING NOTES]" in original_content:
                    # 有旧 working notes：替换掉（保留 [WORKING NOTES] 之前的内容）
                    notes_index = original_content.index("[WORKING NOTES]")
                    original_without_old_notes = original_content[:notes_index].strip()
                    new_user_content = f"{original_without_old_notes}\n\n[WORKING NOTES]\n{working_notes}"
                else:
                    # 没有旧 working notes：追加
                    new_user_content = (
                        f"{original_content}\n\n[WORKING NOTES]\n{working_notes}"
                    )

        # ========== 3. 重新构建 messages ==========
        if has_system:
            system_msg = self.messages[0]
            self.messages = [system_msg, {"role": "user", "content": new_user_content}]
        else:
            self.messages = [{"role": "user", "content": new_user_content}]

        # ========== 4. 保存到 session（确保压缩后的 messages 被持久化）==========
        if self.session and self.session_manager:
            self.session["history"] = self.messages  # 直接引用，不 copy
            # 🔥 修复：使用 await 确保保存完成，避免异步任务未完成就退出导致 working notes 丢失
            await self.session_manager.save_session(self.session)

        # 重置计数器
        # self.last_compression_step = self.current_step

        # 清空 scratchpad（草稿纸用完即弃）
        self.scratchpad.clear()

        return working_notes

    def _is_top_level_microagent(self) -> bool:
        """
        判断是否是 top-level MicroAgent

        Returns:
            bool: 是否是 top-level MicroAgent（parent 是 AgentShell）
        """
        from .agent_shell import AgentShell

        return isinstance(self.parent, AgentShell)

    

    def _format_email_history(self, emails: List[Email]) -> str:
        return _utils.format_email_history(emails, self.name)

    async def execute(
        self,
        run_label: str,  # 必须指定，有语义的名字
        task: str,
        persona: str = None,
        initial_history: Optional[List[Dict]] = None,
        result_params: Optional[Dict[str, str]] = None,
        session: Optional[Dict] = None,
        session_manager=None,
        simple_mode: bool = False,
        exit_actions=[],  # 如果运行哪些动作就退出主循环
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
            initial_history: 初始对话历史（用于恢复记忆，可选）
            result_params: 返回值参数描述（可选）
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
        self._log(logging.INFO, f"{'=' * 60}")
        self._log(logging.INFO, f"MicroAgent '{self.run_label}' starting")
        self._log(logging.INFO, f"Task: {task[:200]}{'...' if len(task) > 200 else ''}")

        # 设置本次执行的参数
        if persona:
            self.persona = persona
        self.task = task
        if simple_mode:
            self.simple_mode = simple_mode
        
        # 保存 session 和 session_manager 引用
        self.session = session
        self.session_manager = session_manager

        # 🆕 Session 兼容性设置：为了与 BaseAgent 和 Skills 兼容
        # 当 session 参数被提供时，设置与 BaseAgent 相同的属性
        if session:
            self.current_session = session
            
            

        # 不设置步数限制，只受时间限制（如果设置了）

        # 重置执行状态
        self.step_count = 0
        self.result = None

        # 恢复或初始化对话历史
        # 优先从 session 获取，否则使用 initial_history
        if session:
            # 从 session 获取 history
            self.messages = session.get("history", []).copy()
            self._log(
                logging.INFO, f"Loaded {len(self.messages)} messages from session"
            )

            # 🆕 总是使用最新的 system prompt（确保 skills 变化立即生效）
            if self.messages and self.messages[0]["role"] == "system":
                self.messages[0] = {
                    "role": "system",
                    "content": self._build_system_prompt(),
                }
                # 添加新的任务输入（只在恢复已有会话时，空 task 跳过）
                if self.task:
                    self._add_message("user", self._format_task_message())
            elif not self.messages:
                self._initialize_session()
                # 🔥 Bug fix: 不要重复添加 user message，_initialize_session 已经添加了
        elif initial_history:
            # 恢复记忆：复制历史记录
            self.messages = initial_history.copy()
            self._log(
                logging.INFO, f"Restoring memory with {len(initial_history)} messages"
            )

            # 🆕 总是使用最新的 system prompt
            if self.messages and self.messages[0]["role"] == "system":
                self.messages[0] = {
                    "role": "system",
                    "content": self._build_system_prompt(),
                }
                # 添加新的任务输入（只在恢复已有会话时，空 task 跳过）
                if self.task:
                    self._add_message("user", self._format_task_message())
            elif not self.messages:
                self._initialize_session()
                # 🔥 Bug fix: 不要重复添加 user message，_initialize_session 已经添加了
        else:
            # 新对话：初始化
            self.messages = []
            self._initialize_session()
        self._log(
            logging.INFO,
            f"Start to '{self.run_label}' with {len(self.messages)} initial messages",
        )
        self._log(
            logging.DEBUG, f"Available actions: {list(self.action_registry.keys())}"
        )
        self._log(
            logging.DEBUG,
            f"Messages:\n{self._format_messages_for_debug(self.messages)}",
        )

        try:
            # 执行 think-negotiate-act 循环
            await self._run_loop(exit_actions)

            # 计算执行时间
            duration = time.time() - start_time

            # ========== 记录结束 ==========
            self._log(
                logging.INFO,
                f"'{self.run_label}' completed in {duration:.2f}s ({self.step_count} steps)",
            )
            self._log(logging.INFO, f"{'=' * 60}")

            # 返回结果
            return self.result

        except Exception as e:
            duration = time.time() - start_time
            self._log(logging.ERROR, f"'{self.run_label}' failed after {duration:.2f}s")
            self._log(logging.ERROR, f"Error: {str(e)}")
            # 打印完整 traceback 以便调试
            import traceback

            self._log(logging.ERROR, f"Traceback:{traceback.format_exc()}")

            # 顶层 MicroAgent 向上传播异常，让 BaseAgent 的错误处理生效（如发邮件通知）
            if self._is_top_level_microagent():
                raise

            return {"error": str(e)}

        finally:
            await self._cleanup_skills()

            # 🔥 确保 session 最终状态被持久化（等待所有后台保存任务完成）
            if self.session and self.session_manager:
                # 保存最新的 session 状态
                self.session["history"] = self.messages
                await self.session_manager.save_session(self.session)

                # 等待一小段时间，让其他可能的异步保存任务完成
                await asyncio.sleep(0.1)

    def _initialize_session(self):
        """初始化对话历史"""
        # 1. System Prompt
        system_prompt = self._build_system_prompt()
        self.messages.append({"role": "system", "content": system_prompt})

        # 2. 任务描述（空 task 跳过，邮件通过 signal 进入）
        if self.task:
            task_message = self._format_task_message()
            self.messages.append({"role": "user", "content": task_message})

    def _build_system_prompt(self) -> str:
        """每轮渲染 system prompt：注入 core_prompt 到模板"""
        core = self.get_core_prompt()
        if "$core_prompt" in self.system_prompt:
            self.system_prompt = self.system_prompt.replace("$core_prompt", core)
        else:
            self.system_prompt += "\n\n" + core
        return self.system_prompt

    def get_core_prompt(self) -> str:
        """Core 层 prompt：加载 core_prompt.md 模板，注入 actions list 和 md skills"""
        template = self.root_agent.get_prompt_template("CORE_PROMPT")

        actions_list = self._format_skills_overview()

        md_skill_section = ""
        if self.md_skills:
            md_skill_section = self._build_md_skill_section_from_dict()

        return (
            template
            .replace("$actions_list", actions_list)
            .replace("$md_skill_section", md_skill_section)
        )

    def _build_md_skill_section_from_dict(self) -> str:
        """从 self.md_skills dict 生成扩展技能库文本段"""
        if not self.md_skills:
            return ""

        lines = [
            "#### B. 扩展技能库 (Procedural Skills)",
            f"你有{len(self.md_skills)}个额外扩展技能存放在 `~/SKILLS/` 目录。每个子目录对应一个技能，目录内包含 skill.md 描述文件。",
            "如果需要使用扩展技能，先列目录，看有什么技能（目录名代表了技能的名字）",
            "如果名字看上去可能是你需要的，就继续读里面的 skill.md 的开头，判断是否真的是你需要的技能",
            "如果是需要的技能，就继续阅读，理解如何使用。扩展技能的命令通常要通过 bash 执行",
            "",
            "可用扩展技能：",
        ]
        for skill_name, description in self.md_skills.items():
            lines.append(f"- **{skill_name}**: {description}")

        return "\n".join(lines)

    def _format_actions_list(self) -> str:
        """格式化可用 actions 列表（新架构：按 skill 分组）"""
        # 委托给 _format_skills_overview
        return self._format_skills_overview()

    def _format_skills_overview(self) -> str:
        """
        格式化 skills 概览（按 skill 分组）

        格式：
        **skill_name**: skill 描述
          • action1: action1_short_desc
          • action2: action2_short_desc
          • action3: action3_short_desc
        """
        lines = []

        # 遍历 _by_skill
        for skill_name, actions in self.action_registry["_by_skill"].items():
            # 获取 skill 描述
            skill_desc = self._get_skill_description(skill_name)

            # 添加 skill 名称和描述
            if skill_desc:
                lines.append(f"**{skill_name}**: {skill_desc}")
            else:
                lines.append(f"**{skill_name}**:")

            # 添加 actions 列表（每个 action 一行，包含 short_desc）
            for action_name, method in actions.items():
                short_desc = getattr(method, "_action_short_desc", None)
                if short_desc:
                    lines.append(f"  • {action_name}: {short_desc}")
                else:
                    # 如果没有 short_desc，只显示 action_name
                    lines.append(f"  • {action_name}")

            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def _get_skill_description(self, skill_name: str) -> str:
        """
        获取 skill 的描述

        从 Python Skills 的 _skill_description 属性获取
        """
        # 检查 Python Skills
        for cls in self.__class__.__mro__:
            if hasattr(cls, "_skill_description") and cls.__name__.endswith("Mixin"):
                # 检查是否是匹配的 skill
                cls_skill_name = self._infer_skill_name(cls.__name__)
                if cls_skill_name == skill_name:
                    return cls._skill_description

        # 默认描述
        return f"{skill_name} skill"

    def _format_task_message(self) -> str:
        """格式化任务消息"""
        # msg = f"[💡NEW SIGNAL]\n{self.task}\n"

        # return msg
        return self.task

    def _format_messages_for_debug(self, messages: List[Dict]) -> str:
        return _utils.format_messages_for_debug(messages)

    async def _think_with_system_failure_recovery(self):
        """
        包装 brain.think_with_retry，处理系统性故障（网络超时、服务不可用等）
        格式问题由 think_with_retry 内部处理
        """
        try:
            return await self.brain.think_with_retry(
                initial_messages=self.messages,
                parser=self._parse_actions_from_thought,
                action_registry=self.action_registry["_flat"],
                max_retries=3,
            )
        except LLMServiceUnavailableError as e:
            # 系统性故障：等待恢复后重试一次
            self.logger.warning(
                f"⚠️ Systemic LLM failure detected: {str(e)}"
            )

            # 1. 等待 5 秒
            await asyncio.sleep(5)

            # 2. 等待 LLM service 恢复
            if not self._is_llm_available():
                self.logger.warning("🔄 Service still unavailable, waiting for recovery...")
                await self._wait_for_llm_recovery()

            # 3. 重试一次
            self.logger.info("🔄 Retrying after service recovery...")
            return await self.brain.think_with_retry(
                initial_messages=self.messages,
                parser=self._parse_actions_from_thought,
                action_registry=self.action_registry["_flat"],
                max_retries=3,
            )

    async def _run_loop(self, exit_actions=[]):
        """信号驱动的执行主循环 - think → launch actions → wait signal → think"""
        start_time = time.time()
        if isinstance(exit_actions, str):
            exit_actions = [exit_actions]
        step_count = 0

        # 将分钟转换为秒
        

        while True:
            # 🔀 检查点1：每次循环开始时检查是否暂停
            await self.root_agent._checkpoint()

            # 🆕 检查是否需要自动压缩（基于 32K tokens）
            if self._should_compress_messages():
                await self._compress_messages()

            

            step_count += 1
            self.step_count = step_count

            # 计算已用时间（用于日志）
            elapsed = time.time() - start_time
            step_info = f"Step {step_count}"
            elapsed_minutes = elapsed / 60
            step_info += f" (时间: {elapsed_minutes:.1f}分钟)"
            self.logger.debug(step_info)
            self._no_action_reflected = False  # 重置本轮是否有 action 被反映的标记
            # 🔀 检查点2：think 之前检查是否暂停
            await self.root_agent._checkpoint()

            # ===== 批量取信号 =====
            # 如果 signal_queue 非空 → drain 所有 signals
            # 如果 signal_queue 空 + 有 running actions → 阻塞等 signal
            # 如果 signal_queue 空 + 无 running actions → 不阻塞（可能进入声明式退出）
            if self.signal_queue.empty() and not self._running_actions:
                # 没有信号也没有 running actions → 跳过信号获取，进入 action 执行后的退出判断
                signals = []
            elif self.signal_queue.empty() and self._running_actions:
                # 有 running actions，阻塞等信号
                signal = await self.signal_queue.get()
                signals = [signal]
                while not self.signal_queue.empty():
                    signals.append(self.signal_queue.get_nowait())
            else:
                # signal_queue 非空，drain 所有
                signals = []
                while not self.signal_queue.empty():
                    signals.append(self.signal_queue.get_nowait())

            # 注入信号为 messages
            await self.inject_signals(signals)

            self.root_agent.update_status(new_status="THINKING")

            # 并行：批量标记邮件已处理 + Think（本地 SQLite 写 vs LLM 网络调用）
            async def _mark_processed():
                if self._pending_processed_ids:
                    ids = self._pending_processed_ids.copy()
                    self._pending_processed_ids.clear()
                    await self.root_agent.post_office.email_db.mark_emails_processed(ids)

            try:

                _, thought = await asyncio.gather(
                    _mark_processed(),
                    self._think_with_system_failure_recovery(),
                )


                # think.brain 的内容已通过 session_events 持久化，不再推 status_history

                action_section_text = thought["[ACTION]"]
                raw_reply = thought.get("[RAW_REPLY]")
                self.logger.debug(f"Raw LLM reply:\n{raw_reply}")
                # 📝 写入 session event: think.brain
                think_event = raw_reply.replace(action_section_text,"").replace("[ACTION]","").replace("[THOUGHTS]","").strip() if raw_reply else None
                if think_event:
                    await self._log_event("think", "brain", {
                        "step_count": step_count,
                        "thought": think_event
                    })
                

                # 2. 检测 actions（多个，保持顺序）
                action_names = await self._detect_actions(action_section_text)

                self.logger.info(f"Detected actions: {action_names}")

                # 📝 写入 session event: action.detected
                if action_names:
                    await self._log_event("action", "detected", {
                        "actions": action_names,
                        "step_count": step_count,
                    })

                # ✅ 状态更新：开始执行 actions
                if action_names:
                    self.root_agent.update_status(new_status="WORKING")

                # 3. 记录 assistant 的思考（只记录一次）
                self._add_message("assistant", raw_reply)

                

                # 4. 分发 actions
                should_break_loop = False

                # 分离 exit_actions 和普通 actions
                exit_action_name = None
                for action_name in action_names:
                    if action_name in exit_actions:
                        exit_action_name = action_name
                        break

                if exit_action_name:
                    # exit_action 仍然同步执行，执行完直接退出循环
                    self.logger.info(f"Executing exit action: {exit_action_name}")
                    self.return_action_name = exit_action_name
                    try:
                        result = await self._execute_action(
                            exit_action_name, action_section_text,
                            action_names.index(exit_action_name) + 1, action_names
                        )
                        self.result = result
                    except Exception:
                        pass
                    should_break_loop = True
                elif action_names:
                    # 统一使用 batch 执行方式（即使是单个 action）
                    action_count = len(action_names)
                    action_desc = f"{action_count} action{'s' if action_count > 1 else ''}"
                    self.logger.info(f"Launching {action_desc}: {action_names}")
                    self._action_counter += 1
                    action_id = f"batch_{self._action_counter}"
                    batch_task = asyncio.create_task(
                        self._run_actions_batch(action_names, action_section_text)
                    )
                    self._running_actions[action_id] = {
                        "task": batch_task,
                        "label": "",
                        "action_names": action_names,
                    }
                    batch_task.add_done_callback(
                        lambda t, aid=action_id: self._on_batch_done(aid, t)
                    )

                # 5. 检查是否需要退出主循环
                if should_break_loop:
                    self.logger.info(f"Loop exit: exit action '{exit_action_name}' completed")
                    break

                # 声明式退出：没有新 action 要执行，且没有 running action 在跑
                if not action_names and not self._running_actions:
                    # 🔍 优先检查是否有疑似幻觉的 action 名称（在通用验证之前）
                    if not self._no_action_reflected:
                        reflect_msg = self._build_no_action_reflect_message(action_section_text, raw_reply or "")
                        if reflect_msg:
                            # 有疑似幻觉 → 给 LLM 一次 reflect 机会（比通用验证更精准）
                            self.logger.info("No action detected but hallucination pattern found, sending reflect prompt")
                            self._no_action_reflected = True
                            self.signal_queue.put_nowait(Signal(
                                type="no_action_reflect",
                                payload={"message": reflect_msg},
                            ))
                            continue

                    # 🆕 仅对 top-level micro agent 进行智能验证
                    if self._is_top_level_microagent():
                        # 第一次检测到无 action：进行智能验证
                        self.logger.info("No actions detected - initiating simple verification for top-level micro agent")

                        # 构建简化的验证提示
                        verification_prompt = self._build_exit_verification_prompt(raw_reply or "")

                        # 独立的 LLM 调用，只传入验证提示（不携带 run_loop 上下文）
                        try:
                            verification_result = await self.brain.think_with_retry(
                                initial_messages=[{"role": "user", "content": verification_prompt}],
                                parser=self._parse_simple_yes_no,
                                max_retries=3,  # 简单分类任务，最多重试 3 次
                            )

                            should_exit = verification_result.get("should_exit", False)
                            self.logger.info(f"Verification result: should_exit={should_exit}")
                            if not should_exit:
                                # LLM 判断应该继续 → 注入继续信号
                                self.logger.info("LLM determined task should continue")
                                # 构建继续提示消息
                                continue_message = """没有发现要执行的动作，如果要执行动作，按格式要求在[ACTIOIN]块下输出动作指令。如果没有，可直接确认所有动作已完成"""

                                # 注入继续信号
                                self.signal_queue.put_nowait(Signal(
                                    type="action_continue",
                                    payload={"message": continue_message},
                                ))
                                continue  # 回到循环顶部，重新进入 think
                            else:
                                # LLM 确认应该退出
                                self.logger.info("LLM confirmed should exit")
                                break

                        except Exception as e:
                            # 验证失败（解析错误、LLM 错误等）→ 降级到原有逻辑
                            self.logger.warning(f"Verification failed: {str(e)}, falling back to legacy logic")
                            # 继续执行原有的退出逻辑
                            pass

                    # 没有疑似幻觉，或者已经 reflect/验证过 → 真正退出
                    self.logger.info("Loop exit: no actions detected, no running actions")
                    break

                # 回到循环顶部，signal_queue.get() 等待
                # BaseAgent 收到新邮件也会 put 信号进来

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
                self.logger.warning(
                    "🔄 Service still unavailable, entering wait mode..."
                )
                await self._wait_for_llm_recovery()

                # 恢复后重试当前步骤
                self.logger.info(
                    "✅ Service recovered after wait, retrying current step"
                )
                step_count -= 1  # 抵消上面的 +=1，重新执行这一步
                continue

    def _is_llm_available(self) -> bool:
        """
        检查 LLM 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        # 向后兼容：如果没有 runtime，假设服务可用
        if not hasattr(self.root_agent, "runtime") or self.root_agent.runtime is None:
            return True

        # 通过 runtime 访问 monitor
        monitor = self.root_agent.runtime.llm_monitor
        if monitor is None:
            return True

        return monitor.llm_available.is_set()

    async def _wait_for_llm_recovery(self):
        """等待 LLM 服务恢复（等待Event）"""
        monitor = self.root_agent.runtime.llm_monitor
        if monitor is None:
            return

        self.logger.info("⏳ Waiting for LLM service recovery...")
        await monitor.llm_available.wait()
        self.logger.info("✅ LLM service recovered!")

    async def _cleanup_skills(self):
        """
        遍历 MRO 中的 SkillMixin，调用其 skill_cleanup()

        Convention: 如果 SkillMixin 定义了 skill_cleanup() 方法，
        在 MicroAgent 生命周期结束时自动调用。同步/异步均可。
        每个 SkillMixin 的 cleanup 独立 try/except，一个失败不影响其他。
        """
        for cls in self.__class__.__mro__:
            if not cls.__name__.endswith("SkillMixin"):
                continue
            cleanup_fn = cls.__dict__.get("skill_cleanup")
            if cleanup_fn is None:
                continue
            try:
                result = cleanup_fn(self)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                self.logger.warning(f"Skill cleanup failed in {cls.__name__}: {e}")

    def _format_combined_results(self, results: list, compress: bool = False) -> str:
        return _utils.format_combined_results(results, compress)

    async def _prepare_feedback_message(
        self, combined_result: str, step_count: int, start_time: float
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
        return f"{combined_result}"

    def _parse_actions_from_thought(
        self, raw_reply: str, action_registry: dict
    ) -> dict:
        return _utils.parse_actions_from_thought(raw_reply, action_registry)

    def _parse_simple_yes_no(self, raw_reply: str) -> dict:
        return _utils.parse_simple_yes_no(raw_reply)

    def _extract_mentioned_actions(self, thought: str) -> List[str]:
        return _utils.extract_mentioned_actions(thought, self.action_registry["_flat"])

    def _parse_and_validate_actions(self, raw_reply: str, mentioned_actions: List[str]) -> Dict[str, Any]:
        return _utils.parse_and_validate_actions(raw_reply, mentioned_actions)

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
{", ".join(mentioned_actions)}

请判断：这些 actions 中，哪些是**真正要执行**的？

**注意：**
- 用户提到，不代表要执行，对每一个action的名字，要根据用户的原话来判断，是要执行它，还是只是提到他。通常用户只会执行一个action
- 如果要做多个action，必须按用户指定的顺序列出来, 
- 在[ACTION]下列出所有**要执行**的 actions，用逗号分隔，保持顺序，不要因为名字相同就合并成一个。


**输出格式：**
```
(可选的）whatever you thinks...
[ACTION]
action1, action2, action3
```

**示例：**
输入：我刚做完了 web_search，现在准备 write plan.txt ,send_mail给老板，然后再write report.txt
（注意，有多个 write，保持顺序）
输出：
```
[ACTION]
write, send_mail, write
```
"""

        # 使用小脑的 think_with_retry
        actions_to_execute = await self.cerebellum.backend.think_with_retry(
            initial_messages=[{"role": "user", "content": prompt}],
            parser=self._parse_and_validate_actions,
            mentioned_actions=mentioned_actions,  # 直接传参给 parser
            max_retries=3,
        )

        self.logger.debug(f"[阶段2] 判断要执行的 actions: {actions_to_execute}")
        return actions_to_execute

    async def _run_actions_batch(
        self, action_names: List[str], thought: str
    ) -> list:
        """
        后台顺序执行一批 actions，返回原始 results 数组

        返回: results 数组（不格式化）
        """
        results = []
        for idx, action_name in enumerate(action_names, start=1):
            # 📝 写入 session event: action.started
            await self._log_event("action", "started", {
                "action_name": action_name,
                "step_count": self.step_count,
            })
            try:
                result = await self._execute_action(
                    action_name, thought, idx, action_names
                )

                # 🆕 检查是否为 NOT_TO_RUN（Cerebellum 判断不执行此 action）
                if result == "NOT_TO_RUN":
                    # 只在日志中记录，不加入 results，也不显示在信号中
                    self.logger.info(f"Action '{action_name}' 判断为不执行，跳过")
                    continue  # 跳过此 action，不加入 results

                # 从 entry 读 label（_execute_action 内已回写）
                action_label = ""
                current_task = asyncio.current_task()
                for _, info in self._running_actions.items():
                    if isinstance(info, dict) and info.get("task") is current_task:
                        action_label = info.get("label", "")
                        break
                results.append({"action_name": action_name, "label": action_label, "result": str(result), "status": "ok"})
                # 📝 写入 session event: action.completed
                await self._log_event("action", "completed", {
                    "action_name": action_name,
                    "action_label": action_label,
                    "result_preview": str(result)[:500] if result else None,
                    "status": "ok",
                })
            except asyncio.CancelledError:
                results.append({"action_name": action_name, "label": "", "result": "Canceled", "status": "canceled"})
                await self._log_event("action", "completed", {
                    "action_name": action_name,
                    "status": "canceled",
                })
                # 标记后续所有 action 为 canceled
                for remaining_name in action_names[idx:]:
                    results.append({"action_name": remaining_name, "label": "", "result": "Canceled", "status": "canceled"})
                break
            except Exception as e:
                results.append({"action_name": action_name, "label": "", "error": str(e), "status": "error"})
                # 📝 写入 session event: action.error
                await self._log_event("action", "error", {
                    "action_name": action_name,
                    "error_message": str(e)[:500],
                })

        return results  # 直接返回数组，不格式化

    async def _execute_action(
        self, action_name: str, thought: str, action_index: int, action_list: List[str]
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
        # 1. 获取方法（使用新的解析逻辑，支持命名空间）
        try:
            method = self._resolve_action(action_name)
        except ValueError as e:
            raise ValueError(f"Action '{action_name}' not found: {e}")

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
**注意：用户一共提到 {total_same_actions} 次 '{action_name}'，这是其中的第 {occurrence} 次{action_name} 。**

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
                temp_msgs.append(
                    {"role": "user", "content": f"[❓NEED CLARIFICATION] {question}"}
                )
                response = await self.brain.think(temp_msgs)
                return response["reply"]

            action_json = await self.cerebellum.parse_action_params(
                intent=thought,
                action_name=action_name,
                param_schema=param_schema,
                brain_callback=brain_clarification,
                task_context=task_context,  # 新增：传递任务上下文
            )

            params = action_json.get("params", {})
            action_label = action_json.get("action_label", "")
            if params == "NOT_TO_RUN":
                return params
        else:
            params = {}
            action_label = ""

        # 将 action_label 存入 _running_actions（让 callback 能拿到）
        current_task = asyncio.current_task()
        for aid, info in self._running_actions.items():
            if isinstance(info, dict) and info.get("task") is current_task:
                info["label"] = action_label
                break

        # 3. 执行方法（✅ 直接调用，无需动态绑定）
        self._log(
            logging.INFO,
            f"[{self.run_label}] Executing {action_name} (task {action_index}/{len(action_list)})",
        )
        result = ""

        try:
            # 💬 特殊处理：ask_user action
            if action_name == "ask_user":
                if not hasattr(self, "root_agent") or not self.root_agent:
                    raise RuntimeError("ask_user requires root_agent")

                question = params.get("question", "")
                if not question:
                    raise ValueError("ask_user requires 'question' parameter")

                # 调用 root_agent.ask_user（会挂起等待用户输入）
                result = await self.root_agent.ask_user(question)
            else:
                # 普通 action：正常调用（异常由 _on_batch_done callback 处理）
                result = await method(**params)
        finally:
            # 记录最后执行的 action 名字
            self.last_action_name = action_name

        return result

    def _add_message(self, role: str, content: str):
        """
        添加消息到对话历史

        智能处理：
        - 如果最后一条 message role 不同 → 直接添加新 message
        - 如果 role 相同：
           a. 如果最后一条 content 是 str → 直接拼接字符串
           b. 如果最后一条 content 是 list（多模态）→ 找到text部分并追加

        如果有 session，自动保存到 session
        """
        if not self.messages or self.messages[-1]["role"] != role:
            # 没有前一条消息，或 role 不同 → 直接添加
            self.messages.append({"role": role, "content": content})
        else:
            # role 相同，需要检查 content 类型
            last_content = self.messages[-1]["content"]

            if isinstance(last_content, str):
                # 最后一条是纯文本 → 直接拼接
                self.messages[-1]["content"] += "\n\n" + content
            elif isinstance(last_content, list):
                # 最后一条是多模态 → 找到text部分并追加
                text_item = next((item for item in last_content if item.get("type") == "text"), None)
                if text_item:
                    # 找到了text项，追加到它的text字段
                    text_item["text"] += "\n\n" + content
                else:
                    # 没有text项，创建一个新的text项
                    last_content.append({"type": "text", "text": content})
            else:
                # 异常情况，直接替换
                self.messages[-1]["content"] = content

        # 如果有 session，自动保存
        if self.session and self.session_manager:
            self.session["history"] = self.messages.copy()
            # 创建异步任务来保存（不阻塞主流程）
            asyncio.create_task(self.session_manager.save_session(self.session))


    def deprecated_get_history(self) -> List[Dict]:
        """
        获取完整的对话历史

        Returns:
            List[Dict]: 完整的对话历史（包括初始历史 + 新增对话）
        """
        return self.messages

    async def _log_event(self, event_type: str, event_name: str, event_detail: dict = None):
        """异步写入 session 事件 + WebSocket 广播"""
        if not self.session or not self.root_agent or not self.root_agent.post_office:
            return
        session_id = self.session.get("session_id")
        if not session_id:
            return

        # DB 写入
        detail_str = json.dumps(event_detail, ensure_ascii=False) if event_detail else None
        await self.root_agent.post_office.email_db.insert_session_event(
            owner=self.root_agent.name,
            session_id=session_id,
            event_type=event_type,
            event_name=event_name,
            event_detail=detail_str,
        )

        # WebSocket 广播
        if self.root_agent._broadcast_message_callback:
            message = {
                "type": "SESSION_EVENT",
                "agent_name": self.root_agent.name,
                "session_id": session_id,
                "data": {
                    "event_type": event_type,
                    "event_name": event_name,
                    "event_detail": event_detail,
                    "timestamp": datetime.now().isoformat(),
                }
            }
            asyncio.create_task(self.root_agent._broadcast_message_callback(message))

    def _get_log_context(self) -> dict:
        """提供日志上下文变量"""
        return {"label": self.run_label or "unknown", "name": self.name}
