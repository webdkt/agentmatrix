from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict

@dataclass
class AgentEvent:
    event_type: str        # THINKING, MAIL_SENT, TOOL_USE...
    source: str
    source_status: str
    content: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self):
        return {
            "type": self.event_type,
            "source": self.source,
            "source_status": self.source_status,
            "content": self.content,
            "payload": self.payload,
            "time": self.timestamp.isoformat()
        }