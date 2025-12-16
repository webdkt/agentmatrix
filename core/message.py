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
    
    def __repr__(self):
        reply_mark = f" (Re: {self.in_reply_to[:8]})" if self.in_reply_to else ""
        return f"<Email {self.id[:8]} From:{self.sender} To:{self.recipient}{reply_mark}>"

    def __str__(self):
        return textwrap.dedent(f"""
            ==== Mail  ====
            From: {self.sender}
            To: {self.recipient}
            Subject: {self.subject}
            Date: {self.timestamp}   

            {self.body}
            =======================
        """)
