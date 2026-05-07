from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from codex_remote_control.config import AppConfig


class WorkspaceNotAllowedError(ValueError):
    pass


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class WorkspaceCommandError(RuntimeError):
    def __init__(self, args: list[str], result: CommandResult) -> None:
        super().__init__(f"Command failed ({result.exit_code}): {' '.join(args)}")
        self.args_list = args
        self.result = result


class WorkspaceExecutor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ensure_allowed(self, workspace_path: str | Path) -> Path:
        resolved = Path(workspace_path).resolve()
        if not self.config.is_allowed_workspace(resolved):
            raise WorkspaceNotAllowedError(f"Workspace is not allowed: {resolved}")
        return resolved

    def git_status(self, workspace_path: str | Path) -> str:
        return self._run_git(workspace_path, "status", "--short").stdout

    def git_diff_summary(self, workspace_path: str | Path) -> str:
        return self._run_git(workspace_path, "diff", "--stat").stdout

    def run_command(self, workspace_path: str | Path, command: str) -> CommandResult:
        cwd = self.ensure_allowed(workspace_path)
        completed = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def commit(self, workspace_path: str | Path, message: str) -> str:
        self._run_git(workspace_path, "add", "-A")
        self._run_git(workspace_path, "commit", "-m", message)
        return self._run_git(workspace_path, "rev-parse", "--short", "HEAD").stdout.strip()

    def _run_git(self, workspace_path: str | Path, *args: str) -> CommandResult:
        cwd = self.ensure_allowed(workspace_path)
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        result = CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if result.exit_code != 0:
            raise WorkspaceCommandError(["git", *args], result)
        return result
