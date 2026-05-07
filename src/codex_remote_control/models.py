from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


class PermissionLevel(StrEnum):
    READ = "read"
    WORK = "work"
    RELEASE = "release"


class PendingActionKind(StrEnum):
    COMMIT = "commit"


@dataclass(frozen=True)
class PendingAction:
    kind: PendingActionKind
    payload: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class Task:
    id: int
    user_id: str
    title: str
    workspace_path: Path
    permission: PermissionLevel
    status: TaskStatus
    summary: str
    last_user_instruction: str
    pending_action: PendingAction | None
    created_at: datetime
    updated_at: datetime


def now_utc() -> datetime:
    return datetime.now(UTC)
