"""
Readable ID Generator - 生成可读的 session_id 和 task_id

格式: {subject关键词}-{YYMMDDHHMM}-{4位随机码}
例如: write-report-2503261430-a3f2
"""

import re
import string
import random
from datetime import datetime


def sanitize(text: str, max_length: int = 10) -> str:
    """
    清理文本，只保留安全的文件名字符

    Args:
        text: 原始文本
        max_length: 最大长度（字符数）

    Returns:
        清理后的文本

    Examples:
        >>> sanitize("帮我写一个报告")
        '帮我写一个报告'
        >>> sanitize("Write Report: 2024")
        'Write-Report-2024'
        >>> sanitize("test@file#name")
        'test-file-name'
    """
    if not text:
        return ""

    # 移除特殊字符，只保留字母、数字、中文、连字符、下划线
    sanitized = re.sub(r'[^\w\u4e00-\u9fff]+', '-', text)
    sanitized = sanitized.strip('-')

    if not sanitized:
        return ""

    # 截取指定长度
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def generate_readable_id(subject: str = "") -> str:
    """
    生成可读的 ID

    格式: {subject关键词}-{YYMMDDHHMM}-{4位随机码}

    Args:
        subject: 邮件主题（可能为空）

    Returns:
        可读 ID，例如: "write-report-2503261430-a3f2"
    """
    # 1. 清理 subject
    clean_subject = sanitize(subject)

    # 如果为空，使用默认前缀
    if not clean_subject:
        clean_subject = "task"

    # 2. 生成时间戳（YYMMDDHHMM）
    now = datetime.now()
    time_str = now.strftime("%y%m%d%H%M")

    # 3. 生成随机码（4位：小写字母 + 数字）
    chars = string.ascii_lowercase + string.digits
    random_str = ''.join(random.choices(chars, k=4))

    # 4. 组合
    readable_id = f"{clean_subject}-{time_str}-{random_str}"

    return readable_id
