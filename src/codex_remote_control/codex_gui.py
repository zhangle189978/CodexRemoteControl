from __future__ import annotations

import subprocess
from pathlib import Path


class CodexGuiClient:
    def __init__(self, script_path: str | Path | None = None, timeout: float = 30.0) -> None:
        self.script_path = Path(script_path) if script_path is not None else _default_script_path()
        self.timeout = timeout

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        del thread_id
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script_path),
            instruction,
            "-InputMode",
            "SendKeys",
            "-SubmitKey",
            "ClickButton",
        ]
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            raise RuntimeError(
                output or f"Codex GUI injection failed with exit code {result.returncode}"
            )
        return output or "Codex GUI injection submitted."


def _default_script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "inject_codex_gui.ps1"
