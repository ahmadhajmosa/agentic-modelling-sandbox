from __future__ import annotations

import json
from pathlib import Path

from .observations import ActionObservation


HISTORY_DIR = ".ams"
HISTORY_FILE = "history.jsonl"


def history_path(workspace: Path) -> Path:
    return workspace / HISTORY_DIR / HISTORY_FILE


def append_observation(workspace: Path, observation: ActionObservation) -> None:
    path = history_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(observation.model_dump_json() + "\n")


def load_observations(workspace: Path, limit: int = 20) -> list[dict]:
    path = history_path(workspace)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines[-limit:] if line.strip()]
