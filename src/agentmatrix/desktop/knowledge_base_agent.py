"""
KnowledgeBaseAgent — 知识库管理 Agent

在 BaseAgent 基础上，提供：
- Wiki 目录结构管理（多知识库支持）
- 知识库上下文注入到 MicroAgent prompt
- 消息压缩时保护 wiki context 标签
- 知识库生命周期管理
"""

import re
import logging
from pathlib import Path
from typing import Optional

from .base_agent import BaseAgent
from .skills.knowledge_base._shared import KBRegistry

logger = logging.getLogger(__name__)

_WIKI_CONTEXT_RE = re.compile(r'<wiki-context>.*?</wiki-context>', re.DOTALL)


class KnowledgeBaseAgent(BaseAgent):
    """知识库管理 Agent

    维护一个持续演化的 wiki 知识库，为用户和其他 Agent 提供知识服务。

    核心特性：
    1. 多知识库支持 — 每个知识库有独立的 wiki 目录和数据库
    2. 用户首次使用必须创建知识库（create_kb wizard）
    3. 消息压缩时保护 <wiki-context> 标签
    4. Schema 驱动：每个知识库有自己的信息类型、关系和目录结构
    """

    _current_kb: str = ""
    _cached_wiki_stats: dict = None  # tree summary string

    @property
    def wiki_root(self) -> Path:
        return self.runtime.paths.wiki_dir

    async def _on_activate_session(self, session, first_signal=None):
        """会话激活时：从 task_id 或 metadata 恢复 current_kb，缓存统计信息"""
        await super()._on_activate_session(session, first_signal)

        task_id = session.get("task_id", "")
        metadata = session.setdefault("metadata", {})

        # 1. 从 task_id 解析 KB 名（kb-chat-{kbName} 模式）
        if task_id.startswith("kb-chat-"):
            self._current_kb = task_id[len("kb-chat-"):]
        # 2. 从 metadata 恢复
        elif metadata.get("current_kb"):
            self._current_kb = metadata["current_kb"]
        # 3. fallback：自动选第一个
        elif not self._current_kb:
            available = KBRegistry.list_all(self.wiki_root)
            if available:
                self._current_kb = available[0]

        # 持久化到 metadata
        if self._current_kb:
            metadata["current_kb"] = self._current_kb

        # 缓存 wiki 目录摘要（供 system prompt 使用）
        if self._current_kb:
            try:
                ns = await KBRegistry.get_or_create(self._current_kb, self.wiki_root)
                self._cached_wiki_stats = ns.wiki_manager.get_tree_summary()
            except Exception as e:
                logger.warning(f"缓存 wiki 目录摘要失败: {e}")
                self._cached_wiki_stats = "（无法读取知识库目录）"
        else:
            self._cached_wiki_stats = ""

    def _create_micro_agent(self):
        """创建 MicroAgent 时注入当前知识库信息"""
        micro = super()._create_micro_agent()
        micro._current_kb = self._current_kb
        return micro

    def _assemble_system_prompt(self, micro_agent):
        """在 system prompt 中注入 wiki context（知识库根目录、Schema、目录概览、问答工作流）"""
        prompt = super()._assemble_system_prompt(micro_agent)

        if not self._current_kb:
            return prompt

        ns = KBRegistry.get(self._current_kb)
        if ns is None:
            return prompt

        try:
            schema = ns.wiki_manager.read_schema()
        except OSError:
            schema = ""

        schema_text = schema if schema else "（知识库尚无 Schema，请先创建知识库）"
        wiki_root_path = str(ns.wiki_manager.wiki_root)
        tree_summary = self._cached_wiki_stats or "（无法读取目录概览）"

        context = (
            f"\n<wiki-context>\n"
            f"## 当前知识库: {self._current_kb}\n"
            f"## 知识库根目录: {wiki_root_path}\n"
            f"## 知识库 Schema\n{schema_text}\n"
            f"## 目录概览\n{tree_summary}\n\n"
            f"## 知识库问答工作流\n"
            f"知识库的目录结构是按 Schema 组织的——每个目录对应 Schema 中定义的信息类型。"
            f"利用这个结构来高效定位信息：\n\n"
            f"1. 根据问题主题和 Schema，判断答案可能在哪些目录\n"
            f"2. 用 list_dir 浏览目标目录，根据文件名确定候选页面\n"
            f"3. 阅读候选页面寻找答案：\n"
            f"   - 短页面用 read_txt_file 直接读\n"
            f"   - 长页面或只需提取特定信息时，用 sub_agent_reader 隔离上下文"
            f"（read_instruction 要尽量完备，包含需要什么信息、相关上下文、期望格式，"
            f"避免子Agent因信息不足而无法完成任务）\n"
            f"4. 如果通过目录和文件名无法定位，再用 grep 在具体子目录中搜索"
            f"（缩小范围，不要在根目录全量搜索）\n"
            f"5. 综合信息回答，标注来源页面路径；没找到就如实告知\n"
            f"</wiki-context>\n"
        )
        return context + prompt

    async def compress_messages(self, agent) -> None:
        """压缩消息时保护 <wiki-context> 标签内容"""
        current_context = self._extract_wiki_context(agent.messages)

        for msg in agent.messages:
            c = msg.get("content")
            if isinstance(c, str):
                msg["content"] = _WIKI_CONTEXT_RE.sub('[知识库结构已加载]', c)

        try:
            await super().compress_messages(agent)
        finally:
            if current_context:
                self._inject_wiki_context_to_messages(agent.messages, current_context)

    async def generate_working_notes(self, messages, focus_hint=""):
        """生成 Working Notes 时保留 wiki 上下文摘要"""
        working_copy = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                cleaned = _WIKI_CONTEXT_RE.sub('[知识库结构已加载]', content)
                msg_copy = dict(msg)
                msg_copy["content"] = cleaned
                working_copy.append(msg_copy)
            else:
                working_copy.append(msg)

        wiki_hint = (
            "注意：<wiki-context> 中的知识库结构信息会在压缩后自动注入到消息上下文中，"
            "不需要在 Working Notes 中详细记录这些内容，只需记住'知识库已加载'即可。"
        )
        enhanced_focus = (focus_hint + "\n" + wiki_hint) if focus_hint else wiki_hint

        return await super().generate_working_notes(working_copy, focus_hint=enhanced_focus)

    # ==========================================
    # Wiki Context 静态工具方法
    # ==========================================

    @staticmethod
    def _extract_wiki_context(messages):
        """从消息历史中提取最新的 <wiki-context> 内容块"""
        for msg in reversed(messages):
            c = msg.get("content", "")
            if isinstance(c, str):
                match = _WIKI_CONTEXT_RE.search(c)
                if match:
                    return match.group(0)
        return None

    @staticmethod
    def _inject_wiki_context_to_messages(messages, context_content):
        """将 wiki-context 内容注入到第一条 user message 的开头"""
        for msg in messages:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                msg["content"] = f"{context_content}\n\n{msg['content']}"
                return True
        return False