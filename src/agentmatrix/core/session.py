from dataclasses import dataclass, field
from typing import List, Dict
from dataclasses import asdict

@dataclass
class TaskSession:
    session_id: str          # 等于触发该任务的原始邮件 ID
    original_sender: str     # 谁派的活
    history: List[Dict]      # 对话历史
    status: str = "RUNNING"  # RUNNING, WAITING
    user_session_id: str = None  # 关联的用户会话 ID


    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # 可以在这里做一些类型转换，比如把字符串转回 datetime
        return cls(**data)