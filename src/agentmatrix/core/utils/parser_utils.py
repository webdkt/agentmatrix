"""
AgentMatrix 通用 Parser 工具

提供各种 LLM 输出解析器，配合 think_with_retry 使用。
"""

import json
import re


def working_notes_parser(raw_reply: str) -> dict:
    """
    解析 working notes 生成结果（提取 Markdown 内容）

    期望格式：
    - 纯 Markdown 文本
    - 或包裹在 ```markdown ... ``` 中的内容

    验证要求：
    - 必须包含至少一个二级标题 (## ...)
    - 必须包含 "## 🧠 关键上下文" 或 "## 关键上下文" 区域（兜底）

    Args:
        raw_reply: LLM 的原始输出

    Returns:
        {
            "status": "success" | "error",
            "content": str (Markdown 格式的 working notes),
            "feedback": str (仅错误时)
        }
    """
    # 1. 提取 Markdown 内容（去除 code block）
    content = raw_reply.strip()

    if "```markdown" in content:
        match = re.search(r"```markdown\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            content = match.group(1)
    elif "```" in content:
        match = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL)
        if match:
            content = match.group(1)

    # 2. 验证是否包含二级标题
    if "##" not in content:
        return {
            "status": "error",
            "feedback": "Working Notes 必须包含至少一个二级标题 (## ...) 用于组织信息结构",
        }

    # 3. 验证是否包含兜底区域
    # 支持多种可能的写法：## 🧠 关键上下文, ## 关键上下文, ## Context 等
    has_context_section = bool(
        re.search(r"##\s*[🧠\s]*关键上下文", content)
        or re.search(r"##\s*Context", content, re.IGNORECASE)
        or re.search(r"##\s*全局上下文", content)
    )

    if not has_context_section:
        return {
            "status": "error",
            "feedback": "Working Notes 必须包含一个兜底区域，建议使用 '## 🧠 关键上下文' 或 '## 关键上下文'",
        }

    # 4. 成功，返回 Markdown 内容
    return {"status": "success", "content": content.strip()}
