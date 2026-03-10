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
    user_session_id: Optional[str] = None  # 用于区分不同用户会话
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据，包括附件信息等
    
    def __repr__(self):
        reply_mark = f" (Re: {self.in_reply_to[:8]})" if self.in_reply_to else ""
        attachment_count = len(self.attachments)
        attachment_mark = f" [{attachment_count} attachment(s)]" if attachment_count > 0 else ""
        return f"<Email {self.id[:8]} From:{self.sender} To:{self.recipient}{reply_mark}{attachment_mark}>"

    @property
    def attachments(self) -> list:
        """获取附件列表"""
        return self.metadata.get('attachments', [])

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
