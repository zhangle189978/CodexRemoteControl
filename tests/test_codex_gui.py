from pathlib import Path

from codex_remote_control.codex_gui import CodexGuiClient


class FakeCompletedProcess:
    returncode = 0
    stdout = "submitted"
    stderr = ""


def test_gui_client_uses_sendkeys_input(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return FakeCompletedProcess()

    monkeypatch.setattr("codex_remote_control.codex_gui.subprocess.run", fake_run)
    client = CodexGuiClient(script_path=tmp_path / "inject.ps1")

    result = client.run_turn("session-id", "检查 git for Windows 进程", tmp_path)

    command, kwargs = calls[0]
    assert result == "submitted"
    assert command[command.index("-InputMode") + 1] == "SendKeys"
    assert "-RestoreClipboard" not in command
    assert kwargs["cwd"] == tmp_path
