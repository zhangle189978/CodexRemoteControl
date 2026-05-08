import json
from pathlib import Path

from codex_remote_control.codex_adapter import CodexAdapter, _command_for_subprocess
from codex_remote_control.models import PermissionLevel
from codex_remote_control.store import TaskStore


class FakeProcessRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(self, command: list[str], cwd: Path) -> str:
        self.calls.append((command, cwd))
        return "Codex finished the remote instruction"


def test_continue_imported_codex_session_uses_exec_resume(tmp_path: Path) -> None:
    store = TaskStore(":memory:")
    task = store.create_task(
        user_id="ding_user",
        title="Desktop handoff",
        workspace_path=tmp_path,
        permission=PermissionLevel.WORK,
        goal="Initial handoff",
    )
    store.set_status(
        task.id,
        task.status,
        summary=json.dumps(
            {
                "source": "codex_session",
                "codex_session_id": "019e0024-4186-7440-b23b-0185fd8def85",
                "summary": "用户：继续",
            }
        ),
    )
    task = store.get_task(task.id)
    runner = FakeProcessRunner()
    adapter = CodexAdapter(command="codex-test", process_runner=runner)

    result = adapter.continue_task(task, "从钉钉继续执行")

    assert result.summary == "Codex finished the remote instruction"
    command, cwd = runner.calls[0]
    assert cwd == tmp_path
    assert command[:4] == [
        "codex-test",
        "exec",
        "resume",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    assert "019e0024-4186-7440-b23b-0185fd8def85" in command
    assert "从钉钉继续执行" in command


def test_continue_imported_codex_session_requires_instruction(tmp_path: Path) -> None:
    store = TaskStore(":memory:")
    task = store.create_imported_session_task(
        user_id="ding_user",
        title="Desktop handoff",
        workspace_path=tmp_path,
        codex_session_id="019e0024-4186-7440-b23b-0185fd8def85",
        summary_text="用户：历史摘要不能当成新指令",
    )
    runner = FakeProcessRunner()
    adapter = CodexAdapter(command="codex-test", process_runner=runner)

    result = adapter.continue_task(task, "")

    assert "请在 /继续 后写具体指令" in result.summary
    assert not result.changed
    assert runner.calls == []


def test_continue_non_imported_task_keeps_local_summary() -> None:
    store = TaskStore(":memory:")
    task = store.create_task(
        user_id="ding_user",
        title="Plain task",
        workspace_path=Path("."),
        permission=PermissionLevel.WORK,
        goal="Initial task",
    )
    runner = FakeProcessRunner()
    adapter = CodexAdapter(command="codex-test", process_runner=runner)

    result = adapter.continue_task(task, "普通继续")

    assert result.summary == "普通继续"
    assert runner.calls == []


def test_windows_cmd_shim_runs_through_cmd_exe() -> None:
    command = _command_for_subprocess(
        [r"C:\Users\89493\AppData\Roaming\npm\codex.cmd", "exec", "resume"]
    )

    assert command == [
        "cmd.exe",
        "/c",
        r"C:\Users\89493\AppData\Roaming\npm\codex.cmd",
        "exec",
        "resume",
    ]
