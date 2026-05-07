from __future__ import annotations

from dataclasses import dataclass

from codex_remote_control.models import Task


@dataclass(frozen=True)
class CodexResult:
    summary: str
    changed: bool


class CodexAdapter:
    def continue_task(self, task: Task, instruction: str) -> CodexResult:
        summary = instruction or task.last_user_instruction
        return CodexResult(summary=summary, changed=False)
