from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class TaskSession:
    session_id: str          # 等于触发该任务的原始邮件 ID
    original_sender: str     # 谁派的活
    history: List[Dict]      # 对话历史
    status: str = "RUNNING"  # RUNNING, WAITING