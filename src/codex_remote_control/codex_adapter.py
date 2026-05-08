from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codex_remote_control.codex_app_server import (
    CodexAppServerClient,
    CodexAppServerTurnFailed,
    CodexAppServerUnavailable,
)
from codex_remote_control.models import Task


@dataclass(frozen=True)
class CodexResult:
    summary: str
    changed: bool


class AppServerClient(Protocol):
    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str: ...


class CodexAdapter:
    def __init__(
        self,
        command: str = "codex",
        process_runner: Callable[[list[str], Path], str] | None = None,
        app_server_client: AppServerClient | None = None,
    ) -> None:
        self.command = command
        self.process_runner = process_runner or self._run_process
        self.app_server_client = (
            app_server_client
            if app_server_client is not None
            else CodexAppServerClient(command)
            if process_runner is None
            else None
        )

    def continue_task(self, task: Task, instruction: str) -> CodexResult:
        codex_session_id = _codex_session_id(task.summary)
        if codex_session_id:
            prompt = instruction.strip()
            if not prompt:
                return CodexResult(
                    summary="请在 /继续 后写具体指令，例如：/继续 继续实现并运行测试。",
                    changed=False,
                )
            if self.app_server_client is not None:
                try:
                    output = self.app_server_client.run_turn(
                        codex_session_id,
                        prompt,
                        task.workspace_path,
                    )
                    return CodexResult(summary=output, changed=True)
                except CodexAppServerTurnFailed as error:
                    return CodexResult(
                        summary=f"Codex app-server turn failed: {error}",
                        changed=True,
                    )
                except CodexAppServerUnavailable:
                    pass
            output = self.process_runner(
                [
                    self.command,
                    "exec",
                    "resume",
                    "--dangerously-bypass-approvals-and-sandbox",
                    codex_session_id,
                    prompt,
                ],
                task.workspace_path,
            )
            return CodexResult(summary=output, changed=True)
        summary = instruction or task.last_user_instruction
        return CodexResult(summary=summary, changed=False)

    def _run_process(self, command: list[str], cwd: Path) -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "last_message.txt"
            command_with_output = [*command[:4], "-o", str(output_path), *command[4:]]
            try:
                result = subprocess.run(
                    _command_for_subprocess(command_with_output),
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60 * 60,
                    check=False,
                )
            except OSError as error:
                return f"Codex resume failed before start: {error}"
            if output_path.exists():
                output = output_path.read_text(encoding="utf-8").strip()
                if output:
                    return output
            combined = (result.stdout + result.stderr).strip()
            if result.returncode != 0:
                return combined or f"Codex resume failed with exit code {result.returncode}"
            return combined or "Codex resume completed without a final message."


def _codex_session_id(summary: str) -> str:
    if not summary:
        return ""
    try:
        value = json.loads(summary)
    except json.JSONDecodeError:
        return ""
    if not isinstance(value, dict) or value.get("source") != "codex_session":
        return ""
    session_id = value.get("codex_session_id")
    return session_id if isinstance(session_id, str) else ""


def _command_for_subprocess(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = shutil.which(command[0]) or command[0]
    suffix = Path(executable).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", executable, *command[1:]]
    return [executable, *command[1:]]
