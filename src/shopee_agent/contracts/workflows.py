from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowInstance(BaseModel):
    workflow_id: str = Field(default_factory=lambda: f"wf_{uuid4().hex}")
    workflow_type: str
    version: str
    subject_id: str
    current_state: str
    status: WorkflowStatus = WorkflowStatus.RUNNING
    event_id: str
    data: dict = Field(default_factory=dict)
