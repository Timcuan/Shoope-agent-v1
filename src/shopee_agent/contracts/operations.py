from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TaskSeverity(str, Enum):
    P0 = "P0"  # Critical (e.g. auth failure, imminent SLA breach)
    P1 = "P1"  # High (e.g. stockout on high-velocity item)
    P2 = "P2"  # Medium (e.g. unhandled chat message, return request)
    P3 = "P3"  # Low (e.g. suggestion, generic alert)


class TaskStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    WAITING = "waiting"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class OperatorTask(BaseModel):
    task_id: str
    category: str
    subject_id: str
    shop_id: str = "demo_shop"
    severity: TaskSeverity
    title: str
    summary: str
    status: TaskStatus = TaskStatus.OPEN
    due_at: datetime | None = None
    is_notified: bool = False
