import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import textwrap

@dataclass
class Email:
    sender: str
    recipient: str
    subject: str
    body: str
    in_reply_to: Optional[str] = None  # 核心：引用链
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: Optional[str] = None  # 用于区分不同用户会话
    sender_session_id: Optional[str] = None  # 发件人的 session_id（发送时设置）
    recipient_session_id: Optional[str] = None  # 收件人的 session_id（接收时更新）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据，包括附件信息等

    def __post_init__(self):
        # 防御 DB 恢复时 metadata 为 None 或字符串的情况
        if self.metadata is None:
            self.metadata = {}
        elif isinstance(self.metadata, str):
            import json
            try:
                self.metadata = json.loads(self.metadata)
            except (json.JSONDecodeError, TypeError):
                self.metadata = {}
    
    def __repr__(self):
        reply_mark = f" (Re: {self.in_reply_to[:8]})" if self.in_reply_to else ""
        attachment_count = len(self.attachments)
        attachment_mark = f" [{attachment_count} attachment(s)]" if attachment_count > 0 else ""
        return f"<Email {self.id[:8]} From:{self.sender} To:{self.recipient}{reply_mark}{attachment_mark}>"

    @property
    def attachments(self) -> list:
        """获取附件列表"""
        return self.metadata.get('attachments', [])

    # ==========================================
    # Signal 协议
    # ==========================================

    @property
    def signal_type(self) -> str:
        return "email"

    @property
    def signal_id(self) -> Optional[str]:
        return self.id

    def to_text(self) -> str:
        text = f"[新邮件] 来自 {self.sender}: {self.subject}\n{self.body}"
        if self.attachments:
            text += "\n" + "\n".join(
                f"附件已保存在 {att.get('container_path', att.get('filename', ''))}"
                for att in self.attachments
            )
        return text

    def log_detail(self) -> Dict[str, Any]:
        return {
            "signal_type": "email",
            "email_id": self.id,
            "sender": self.sender,
        }

    def __str__(self):
        attachment_list = ""
        attachment_notice = ""
        if self.attachments:
            # 附件列表（显示给用户看）
            attachment_list = "\nAttachments:\n" + "\n".join(f"  - {att.get('filename', 'Unknown')}" for att in self.attachments)
            # 附件保存路径提示（显示给 Agent 看）
            attachment_notice = "\n" + "\n".join(f"附件已保存在 {att.get('container_path', att.get('filename', ''))}" for att in self.attachments)

        return textwrap.dedent(f"""
            ===== Mail =====
            From: {self.sender}
            To: {self.recipient}
            Subject: {self.subject}
            Date: {self.timestamp}{attachment_list}

            {self.body}{attachment_notice}
            ===== End of Mail ======
        """)
