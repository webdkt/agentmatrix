"""
Token 估算工具

提供文本和消息列表的 token 估算功能。
"""

import re
from typing import List, Dict


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量

    Token 估算规则（参考 OpenAI 官方）：
    - 英文：Token 数 ≈ 单词数 × 1.3（100 tokens ≈ 75 words）
    - 中文：Token 数 ≈ 字数 × (1 到 1.5)
    - 代码/特殊符号：普通文本的 1.5-2 倍

    Args:
        text: 要估算的文本

    Returns:
        估算的 token 数量
    """
    # 统计中文字符数
    chinese_chars = len([c for c in text if "\u4e00" <= c <= "\u9fff"])

    # 统计英文单词数（按空格分词）
    english_words = len(re.findall(r"\b[a-zA-Z]+\b", text))

    # 统计特殊字符/代码符号（非中英文、空格、换行）
    special_chars = len(
        [
            c
            for c in text
            if not ("\u4e00" <= c <= "\u9fff")  # 非中文
            and not c.isalpha()  # 非字母
            and not c.isspace()
        ]
    )  # 非空白

    # 估算 token 数
    # 中文：1-1.5 倍（取平均 1.3）
    # 英文：单词数 × 1.3
    # 特殊符号：数量 × 2（保守估计）
    estimated = int(chinese_chars * 1.3 + english_words * 1.3 + special_chars * 2)

    return estimated


def estimate_messages_tokens(messages: List[Dict]) -> int:
    """
    估算 messages 列表的总 token 量

    Args:
        messages: 消息列表，每个消息包含 'content' 字段

    Returns:
        估算的总 token 数量
    """
    return sum(estimate_tokens(m.get("content", "")) for m in messages)


def format_session_messages(messages: List[Dict]) -> str:
    """
    格式化对话历史为可读文本

    过滤掉 system message，只保留 user 和 assistant 的对话。

    Args:
        messages: 消息列表

    Returns:
        str: 格式化的对话历史
    """
    # 过滤掉 system message，只保留对话历史
    session_msgs = [m for m in messages if m.get("role") != "system"]

    return "\n".join([f"{m['role']}: {m['content']}" for m in session_msgs])
