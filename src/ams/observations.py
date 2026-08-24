from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import Field

from .schemas import StrictModel


class PolicyDecision(StrictModel):
    allowed: bool
    rule: str
    message: str


class ActionObservation(StrictModel):
    schema_version: Literal["ams/observation-v1"] = "ams/observation-v1"
    action_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action_type: str
    status: Literal["success", "denied", "error", "timeout"]
    policy: PolicyDecision
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: int = 0
    artifacts_changed: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
