"""
ID Generator - 统一的ID生成工具

职责：
- 生成session_id（固定12字符）
- 生成email_id（完整UUID）
- 生成外部Message-ID
- Subject标记的添加/移除/提取
"""

import uuid
import re
from typing import Optional


class IDGenerator:
    """统一的ID生成器"""

    # Session ID固定长度：12字符
    SESSION_ID_LENGTH = 12

    # Session标记的正则模式
    SESSION_TAG_PATTERN = r'#([a-f0-9]{12})\b'

    @staticmethod
    def generate_session_id() -> str:
        """
        生成session_id（固定12字符）

        使用UUID的前12位，确保：
        - 足够唯一（UUID的熵）
        - 适合subject显示
        - 不太长，不影响阅读

        Returns:
            session_id，例如：a1b2c3d4e5f6

        Examples:
            >>> session_id = IDGenerator.generate_session_id()
            >>> len(session_id)
            12
            >>> assert re.match(r'^[a-f0-9]{12}$', session_id)
        """
        full_uuid = str(uuid.uuid4()).replace('-', '')
        return full_uuid[:IDGenerator.SESSION_ID_LENGTH]

    @staticmethod
    def generate_email_id() -> str:
        """
        生成email_id（完整UUID）

        Email ID使用完整UUID，确保全局唯一性。

        Returns:
            完整UUID，例如：a1b2c3d4-e5f6-7890-abcd-ef1234567890
        """
        return str(uuid.uuid4())

    @staticmethod
    def add_session_tag(subject: str, session_id: str) -> str:
        """
        在subject中添加session标记

        如果subject已经有session标记，会先移除再添加新的。
        避免重复添加标记。

        Args:
            subject: 原始subject
            session_id: session_id（12字符）

        Returns:
            添加了标记的subject，例如："帮我写报告 #a1b2c3d4e5f6"

        Examples:
            >>> IDGenerator.add_session_tag("帮我写报告", "a1b2c3d4e5f6")
            '帮我写报告 #a1b2c3d4e5f6'
            >>> IDGenerator.add_session_tag("帮我写报告 #xyz123ab4567", "a1b2c3d4e5f6")
            '帮我写报告 #a1b2c3d4e5f6'
        """
        # 去掉已有的标记（避免重复添加）
        clean_subject = IDGenerator.remove_session_tag(subject)

        # 添加标记
        return f"{clean_subject} #{session_id}".strip()

    @staticmethod
    def remove_session_tag(subject: str) -> str:
        """
        从subject中移除session标记

        移除subject末尾的session标记，用于：
        - 清理subject显示
        - 避免重复添加标记
        - 提取原始subject

        Args:
            subject: 可能包含标记的subject

        Returns:
            移除了标记的subject

        Examples:
            >>> IDGenerator.remove_session_tag("帮我写报告 #a1b2c3d4e5f6")
            '帮我写报告'
            >>> IDGenerator.remove_session_tag("帮我写报告")
            '帮我写报告'
        """
        # 匹配 #[字母数字]{12} 在subject末尾
        pattern = r'\s*#[a-f0-9]{12}\s*$'
        return re.sub(pattern, '', subject, flags=re.IGNORECASE).strip()

    @staticmethod
    def extract_session_id(subject: str) -> Optional[str]:
        """
        从subject中提取session_id

        用于EmailProxy接收外部邮件时恢复session。

        Args:
            subject: 可能包含标记的subject

        Returns:
            session_id（12字符，小写），如果没找到返回None

        Examples:
            >>> IDGenerator.extract_session_id("帮我写报告 #a1b2c3d4e5f6")
            'a1b2c3d4e5f6'
            >>> IDGenerator.extract_session_id("帮我写报告")
            None
            >>> IDGenerator.extract_session_id("Re: 帮我写报告 #A1B2C3D4E5F6")
            'a1b2c3d4e5f6'
        """
        # 匹配 #[字母数字]{12}（不区分大小写）
        match = re.search(IDGenerator.SESSION_TAG_PATTERN, subject, flags=re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None

    @staticmethod
    def has_session_tag(subject: str) -> bool:
        """
        检查subject是否包含session标记

        Args:
            subject: 要检查的subject

        Returns:
            True如果包含session标记，否则False

        Examples:
            >>> IDGenerator.has_session_tag("帮我写报告 #a1b2c3d4e5f6")
            True
            >>> IDGenerator.has_session_tag("帮我写报告")
            False
        """
        return IDGenerator.extract_session_id(subject) is not None

    @staticmethod
    def generate_message_id(domain: str) -> str:
        """
        生成外部Message-ID

        符合RFC 5322标准的Message-ID格式。

        Args:
            domain: 域名，例如：agentmatrix.gmail.com

        Returns:
            Message-ID，例如：<a1b2c3d4-e5f6-7890-abcd@agentmatrix.gmail.com>

        Examples:
            >>> msg_id = IDGenerator.generate_message_id("agentmatrix.gmail.com")
            >>> assert msg_id.startswith('<')
            >>> assert msg_id.endswith('@agentmatrix.gmail.com>')
            >>> assert msg_id.endswith('>')
        """
        return f"<{uuid.uuid4()}@{domain}>"

    @staticmethod
    def validate_session_id(session_id: str) -> bool:
        """
        验证session_id格式是否正确

        Args:
            session_id: 要验证的session_id

        Returns:
            True如果格式正确，否则False

        Examples:
            >>> IDGenerator.validate_session_id("a1b2c3d4e5f6")
            True
            >>> IDGenerator.validate_session_id("a1b2c3")
            False
            >>> IDGenerator.validate_session_id("A1B2C3D4E5F6")
            False
        """
        return bool(re.match(r'^[a-f0-9]{12}$', session_id))

    @staticmethod
    def is_internal_email_id(email_id: str) -> bool:
        """
        判断是否是内部email_id（完整UUID格式）

        Args:
            email_id: 要判断的ID

        Returns:
            True如果是完整UUID，否则False
        """
        # UUID格式：xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        return bool(re.match(uuid_pattern, email_id, flags=re.IGNORECASE))
