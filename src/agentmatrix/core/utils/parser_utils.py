"""
AgentMatrix 通用 Parser 工具

提供各种 LLM 输出解析器，配合 think_with_retry 使用。
"""

import json
import re


def working_notes_parser(raw_reply: str) -> dict:
    """
    解析 working notes 生成结果（提取 <working_note> 标签包裹的内容）

    期望格式：
    <working_note>
    ... Markdown 格式的工作笔记 ...
    </working_note>

    标签外的内容会被忽略，只提取标签内的部分。
    这避免了 LLM 的寒暄、解释、确认语等干扰内容被当作 Working Notes。

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        {
            "status": "success" | "error",
            "content": str (Markdown 格式的 working notes),
            "feedback": str (仅错误时)
        }
    """
    # 1. 提取 <working_note> 标签内的内容
    match = re.search(r'<working_note>(.*?)</working_note>', raw_reply, re.DOTALL)

    if match:
        content = match.group(1).strip()
        if content:
            return {"status": "success", "content": content}

    # 2. 没有找到有效的 <working_note> 标签
    # 检查是否有开标签但没有闭标签（LLM 输出被截断的情况）
    if '<working_note>' in raw_reply and '</working_note>' not in raw_reply:
        start_idx = raw_reply.index('<working_note>') + len('<working_note>')
        content = raw_reply[start_idx:].strip()
        if content:
            return {"status": "success", "content": content}

    # 3. 完全没有 <working_note> 标签，要求 LLM 重新格式化
    return {
        "status": "error",
        "feedback": "请用 <working_note> 和 </working_note> 标签包裹你的工作笔记输出。格式示例：\n<working_note>\n## 当前状态\n...\n## 🧠 关键上下文\n...\n</working_note>",
    }