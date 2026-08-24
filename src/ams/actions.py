from __future__ import annotations

from typing import Annotated, Any, Literal
from pydantic import Field

from .schemas import StrictModel


class WriteFileAction(StrictModel):
    type: Literal["write_file"]
    path: str
    content: str


class RunCommandAction(StrictModel):
    type: Literal["run_command"]
    argv: list[str] = Field(min_length=1)


class RunTestsAction(StrictModel):
    type: Literal["run_tests"]
    argv: list[str] = Field(default_factory=lambda: ["pytest", "-q"], min_length=1)


class ReadFileAction(StrictModel):
    type: Literal["read_file"]
    path: str
    max_chars: int | None = Field(default=None, ge=1)


class InvokeCapabilityAction(StrictModel):
    type: Literal["invoke_capability"]
    capability: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class EvaluateCandidateAction(StrictModel):
    type: Literal["evaluate_candidate"]
    split: Literal["train", "validation", "test"] = "validation"
    final: bool = False


ActionRequest = Annotated[
    WriteFileAction | RunCommandAction | RunTestsAction | ReadFileAction | InvokeCapabilityAction | EvaluateCandidateAction,
    Field(discriminator="type"),
]
