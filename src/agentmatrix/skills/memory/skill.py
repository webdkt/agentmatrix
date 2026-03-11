"""
Memory Skill - 核心实现

提供两层实体记忆系统：
- Session 级别记忆（临时信息，会话内有效）
- 全局级别记忆（长期信息，跨会话保留）

核心 Actions：
- recall: 查询实体记忆（合并 session + 全局）
- update_memory: 主动触发压缩 + 持久化

注意：
- Whiteboard 生成由 MicroAgent 内置提供
- Memory Skill 只负责持久化和查询
"""

import asyncio
import json
from typing import List, Dict, Any
from ...core.action import register_action
from .storage import search_entities_merged, append_timeline_events
from .utils import (
    save_whiteboard,
)


class MemorySkillMixin:
    """
    Memory Skill Mixin

    提供实体记忆功能，包括回忆（recall）和更新记忆（update_memory）。

    注意：
    - _compress_messages() 和 _generate_whiteboard_summary() 由 MicroAgent 提供
    - 本类只负责持久化和查询功能
    """

    # 🆕 Skill 级别元数据
    _skill_description = "记忆管理技能：存储、查询、更新实体和事件的记忆。经常update_memory有助于保持注意力"

    _skill_usage_guide = """
使用场景：
- 需要记录和回忆实体（人物、项目等）信息
- 需要记录和回忆历史事件
- 需要更新记忆内容

使用建议：
- 使用 recall 查询实体或事件的记忆
- 使用 update_memory 更新记忆内容

注意事项：
- 记忆会持久化到数据库
- 支持模糊查询
"""

    # ==================== Public Actions ====================

    @register_action(
        "回忆实体或事件。当你需要查询之前提到的实体（人物、项目等）或历史事件时调用此 action。",
        param_infos={
            "entity_name": "要查询的实体名称（如'张三'、'Alpha项目'）",
            "question": "关于该实体的具体问题（如'张三之前的决策是什么？'）"
        }
    )
    async def recall(self, entity_name: str, question: str) -> str:
        """
        回忆实体或事件

        流程：
        1. 精确匹配查找 entity profiles（session + global）
        2. 按 canonical_name 合并拼接
        3. 批量问 LLM（每个 batch 最多 5000 tokens）
        4. 返回第一个能回答的 LLM 结果

        Args:
            entity_name: 要查询的实体名称（精确匹配）
            question: 关于该实体的具体问题

        Returns:
            str: LLM 的答案，或"没有找到相关信息"
        """
        from .parser_utils import recall_answer_parser
        from .utils import split_profiles_by_tokens, format_profiles_batch

        # 1. 查询并合并 profiles（使用 storage 高层 API）
        merged_profiles = await search_entities_merged(
            self.root_agent.workspace_root,
            self.root_agent.name,
            self.root_agent.user_session_id,
            entity_name
        )

        if not merged_profiles:
            return f"没有找到关于'{entity_name}'的相关信息"

        # 2. 按批次处理
        batches = split_profiles_by_tokens(merged_profiles, token_limit=5000)

        # 3. 逐批尝试
        for batch in batches:
            batch_text = format_profiles_batch(batch)

            prompt = f"""用户想回忆关于"{entity_name}"的信息，问题是：{question}

我们现在找到了以下档案卡片（不确定是否符合）：

{batch_text}

请判断这些档案能否回答用户的问题。如果可以，请给出答案；如果不可以，就明确说不可以(can_answer_user: false)。

**重要：必须输出 JSON 格式，包含两个字段：**
- "answer"：字符串类型，存储回答内容
- "can_answer_user"：布尔值类型（true 或 false），表示能否回答用户的问题

JSON 格式示例：
```json
{{
    "answer": "（从档案中提取的回答内容）",
    "can_answer_user": true
}}
```

如果不能回答：
```json
{{
    "answer": "这些档案不包含与用户问题相关的信息",
    "can_answer_user": false
}}
```

仔细阅读后输出你的答案（仅输出 JSON，不要有其他内容）："""

            try:
                # 使用 think_with_retry 获取结构化回答
                result = await self.root_agent.cerebellum.think_with_retry(
                    initial_messages=prompt,
                    parser=recall_answer_parser,
                    max_retries=2
                )

                # result = {"answer": "...", "can_answer_user": true/false}

                if result.get("can_answer_user") is True:
                    return result.get("answer", "找到相关信息")

            except Exception as e:
                # 解析失败，继续下一批
                self.logger.warning(f"Batch 解析失败: {e}")
                continue

        # 所有 batch 都无法回答
        return f"记忆里没有找到相关信息"

    @register_action(
        "更新记忆。当对话告一段落或完成重要信息澄清时调用此 action。可以提示记忆总结重点，如'重点关注财务决策'、'突出实体关系变化'等",
        param_infos={
            "focus_hint": "可选。指导总结重点，如'重点关注财务决策'、'突出实体关系变化'等"
        }
    )
    async def update_memory(self, focus_hint: str = "") -> str:
        """
        更新记忆（主动触发）

        流程：
        1. 调用 MicroAgent 内置的 _compress_messages()（生成 whiteboard 并压缩 messages）
        2. 持久化 whiteboard（如果是 top-level）
        3. 持久化 timeline（如果是 top-level）

        Args:
            focus_hint: 可选参数，指导 LLM 总结重点

        Returns:
            str: "记忆已更新"
        """
        # 1. 调用内置压缩方法（生成 whiteboard 并压缩 messages）
        # 注意：_compress_messages() 由 MicroAgent 提供
        whiteboard = await self._compress_messages()

        # 2. Top-Level: 持久化（仅 top-level 需要持久化）
        if self._is_top_level():
            # 保存 whiteboard（直接调用 utils）
            await self._persist_whiteboard(whiteboard)

            # 生成并追加 timeline events
            messages = self.messages  # 已压缩后的
            events = await self._generate_memory_events(messages)
            await self._persist_timeline(events)

        return "记忆已更新"

    # ==================== 私有方法 ====================

    def _is_top_level(self) -> bool:
        """判断是否是 top-level MicroAgent"""
        from ...agents.base import BaseAgent
        return isinstance(self.parent, BaseAgent)

    async def _generate_memory_events(self, messages: list) -> List[str]:
        """LLM 总结：生成 memory_events（关键事件增量）"""
        from .utils import format_conversation_messages

        prompt = f"""
分析以下对话历史，提取关键事件（用于长期记忆）。

要求：
1. 自包含的完整事件（不含代词）
2. 实体名必须完整
3. 仅包含有长期价值的信息

对话历史：
{format_conversation_messages(messages, max_length=200)}

输出 JSON 列表：
["事件1", "事件2", ...]
"""

        llm = self.root_agent.cerebellum
        response = await llm.generate(prompt)

        # 解析 JSON
        try:
            events = json.loads(response)
            return events if isinstance(events, list) else []
        except json.JSONDecodeError:
            return []

    async def _persist_whiteboard(self, content: str):
        """持久化 whiteboard 到文件"""
        save_whiteboard(
            content,
            self.root_agent.workspace_root,
            self.root_agent.name,
            self.root_agent.user_session_id
        )

    async def _persist_timeline(self, events: List[str]):
        """持久化 timeline 到数据库"""
        await append_timeline_events(
            self.root_agent.workspace_root,
            self.root_agent.name,
            self.root_agent.user_session_id,
            events
        )
