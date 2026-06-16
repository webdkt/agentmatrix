"""
Knowledge Base Skill — 知识库创建与文件阅读辅助

Actions:
- create_kb:       创建知识库
- sub_agent_reader: 派遣子Agent阅读文件（上下文隔离）
"""

import logging
from pathlib import Path
from typing import Optional

from agentmatrix.core.action import register_action
from agentmatrix.core.micro_agent import MicroAgent
from .prompts import KnowledgePrompts
from ._shared import (
    KBRegistry,
    KBInstance,
    resolve_user_path,
)

logger = logging.getLogger(__name__)


def _pass_through_parser(raw_reply: str, **kwargs) -> dict:
    return {"status": "success", "content": raw_reply}


class Knowledge_baseSkillMixin:
    """知识库创建与文件阅读辅助技能"""

    _skill_description = "知识库创建与文件阅读辅助（wiki）"
    _skill_dependencies = ["file", "markdown"]

    # ==================== 辅助方法 ====================

    def _get_wiki_base(self) -> Path:
        return self.root_agent.runtime.paths.wiki_dir

    async def _ensure_schema_dirs(self, ns: KBInstance, schema_content: str):
        """用 MicroAgent + file skill 按 Schema 创建目录结构。"""
        micro = MicroAgent(
            parent=self,
            name=f"kb-dir-setup-{ns.name}",
            available_skills=["file"],
            system_prompt=(
                "你是目录初始化助手。你的任务是根据知识库 Schema 创建目录结构。\n"
                "只创建目录，不写入任何文件内容。完成后返回创建结果。"
            ),
        )
        try:
            await micro.execute(
                run_label=f"create-dirs-{ns.name}",
                task=(
                    f"知识库目录：`{ns.wiki_root}`\n\n"
                    f"以下是此知识库的 Schema：\n\n{schema_content}\n\n"
                    f"请根据 Schema 中「目录结构及用途」部分定义的目录，在知识库目录下创建所有目录。"
                    f"用 list_dir 确认当前结构，然后用 bash 的 mkdir -p 创建。"
                ),
                simple_mode=True,
            )
        except Exception as e:
            logger.warning(f"MicroAgent 创建目录失败: {e}")

    # ==================== 知识库创建 ====================

    @register_action(
        short_desc="创建知识库",
        description=(
            "创建一个新的知识库。"
            "如果提供 draft_path，从文件读取 Schema 并创建知识库（清理草稿文件）。"
            "如果不提供 draft_path，生成初始 Schema 供用户 review。"
        ),
        param_infos={
            "name": "知识库名称（如 work, personal, reading）",
            "description": "描述此知识库的用途和关注领域",
            "draft_path": "Schema 草稿文件路径（可选，提供则直接创建）",
        },
    )
    async def create_kb(self, name: str, description: str = "", draft_path: str = "") -> str:
        import re as _re
        if not name or len(name) < 2 or name.startswith('.') or name.startswith('_') or '..' in name:
            return f"无效的知识库名称 '{name}'。名称至少2个字符，不能以点号或下划线开头，不能包含 '..'。"
        if not _re.match(r'^[a-zA-Z0-9_\-]+$', name):
            return f"无效的知识库名称 '{name}'。只允许字母、数字、下划线和连字符。"

        wiki_base = self._get_wiki_base()
        ns = KBRegistry.get(name)
        if ns:
            if ns.wiki_manager.has_schema():
                return f"知识库 '{name}' 已存在且已有 Schema。"

        ns = await KBRegistry.get_or_create(name, wiki_base)

        if ns.wiki_manager.has_schema():
            return f"知识库 '{name}' 已有 Schema。"

        # 如果提供了 draft_path，从文件读取 Schema
        if draft_path:
            try:
                draft_file = resolve_user_path(draft_path)
                if not draft_file.exists():
                    return f"草稿文件不存在: {draft_path}"
                schema_content = draft_file.read_text(encoding="utf-8")
                if not schema_content.strip():
                    return f"草稿文件为空: {draft_path}"
            except Exception as e:
                return f"读取草稿文件失败: {e}"

            ns.wiki_manager.init_with_schema(schema_content)
            ns.wiki_manager.append_log("create_kb", name, f"描述: {description}")
            self.root_agent._current_kb = name

            # 清理草稿文件
            try:
                draft_file.unlink()
            except Exception:
                pass

            # 按 Schema 目录结构创建缺失目录
            await self._ensure_schema_dirs(ns, schema_content)

            return (
                f"已创建知识库 '{name}'。\n\n"
                f"Schema 已从草稿文件加载并保存。"
            )

        # 没有 draft_path，生成 Schema 供 review
        prompt = KnowledgePrompts.SCHEMA_GENERATION_PROMPT.format(
            name=name,
            description=description or "通用知识库",
        )

        schema_content = await self.root_agent.brain.think_with_retry(
            prompt,
            _pass_through_parser,
            max_retries=2,
        )

        if not schema_content or not isinstance(schema_content, str):
            return f"生成 Schema 失败，请重试 create_kb '{name}'。"

        ns.wiki_manager.init_with_schema(schema_content)
        ns.wiki_manager.append_log("create_kb", name, f"描述: {description}")

        self.root_agent._current_kb = name

        # 按 Schema 目录结构创建缺失目录
        await self._ensure_schema_dirs(ns, schema_content)

        return (
            f"已创建知识库 '{name}'，初始 Schema 已生成。\n\n"
            f"{schema_content}"
        )

    # ==================== 文件阅读 ====================

    @register_action(
        short_desc="派遣子Agent阅读文件[file_path, read_instruction]",
        description=(
            "启动一个临时子Agent阅读指定文件，根据指示提取信息并返回。"
            "用于上下文隔离：避免大文件全文进入当前对话。"
            "适合阅读较长的wiki页面或需要从文件中提取特定信息的场景。"
            "read_instruction 要尽量完备——说明需要什么信息、相关上下文、期望格式，"
            "避免子Agent因信息不足而无法完成任务。"
        ),
        param_infos={
            "file_path": "要阅读的文件路径",
            "read_instruction": "阅读指示，尽量完备地描述需要什么信息及相关上下文",
        },
    )
    async def sub_agent_reader(self, file_path: str, read_instruction: str) -> str:
        micro = MicroAgent(
            parent=self,
            name="kb-reader",
            available_skills=["file"],
            system_prompt=(
                "你是文件阅读助手，不是对话伙伴。\n"
                "你会得到一个文件路径和阅读指示。\n"
                "请使用 read_txt_file 阅读文件（大文件用 start_line/end_line 分批读取），"
                "根据指示提取信息并返回。\n\n"
                "规则：\n"
                '- 如果文件中没有指示所需的信息，返回"未找到相关内容"并列出你实际找到的信息概要\n'
                "- 绝对不要提问，不要请求澄清，尽你所能完成任务\n"
                "- 不要做任何超出阅读指示之外的事情"
            ),
        )
        try:
            result = await micro.execute(
                run_label="kb-reader",
                task=f"请阅读文件：{file_path}\n\n阅读指示：{read_instruction}",
                simple_mode=True,
            )
            return result if isinstance(result, str) else str(result)
        except Exception as e:
            return f"子Agent阅读失败: {e}"
