import json
from pathlib import Path

from codex_remote_control.codex_adapter import CodexAdapter, _command_for_subprocess
from codex_remote_control.codex_app_server import (
    CodexAppServerTurnFailed,
    CodexAppServerUnavailable,
)
from codex_remote_control.models import PermissionLevel
from codex_remote_control.store import TaskStore


class FakeProcessRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []

    def __call__(self, command: list[str], cwd: Path) -> str:
        self.calls.append((command, cwd))
        return "Codex finished the remote instruction"


class FakeAppServerClient:
    def __init__(self, response: str = "POC app-server completed") -> None:
        self.response = response
        self.calls: list[tuple[str, str, Path]] = []

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        self.calls.append((thread_id, instruction, cwd))
        return self.response


class FakeGuiClient:
    def __init__(self, response: str = "Codex GUI submitted text") -> None:
        self.response = response
        self.calls: list[tuple[str, str, Path]] = []

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        self.calls.append((thread_id, instruction, cwd))
        return self.response


class FailingGuiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Path]] = []

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        self.calls.append((thread_id, instruction, cwd))
        raise RuntimeError("gui unavailable")


class FakeSessionSource:
    def __init__(self, reply: str = "") -> None:
        self.reply = reply
        self.count_calls: list[str] = []
        self.wait_calls: list[tuple[str, int]] = []

    def count_key_events(self, session_id: str) -> int:
        self.count_calls.append(session_id)
        return 3

    def count_wait_events(self, session_id: str) -> int:
        self.count_calls.append(session_id)
        return 3

    def wait_for_next_assistant_reply(
        self,
        session_id: str,
        after_event_count: int,
        timeout: float = 180.0,
        interval: float = 1.0,
    ) -> str:
        del timeout, interval
        self.wait_calls.append((session_id, after_event_count))
        return self.reply


class FailingAppServerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Path]] = []

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        self.calls.append((thread_id, instruction, cwd))
        raise CodexAppServerUnavailable("app-server unavailable")


class FailedTurnAppServerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Path]] = []

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        self.calls.append((thread_id, instruction, cwd))
        raise CodexAppServerTurnFailed("context window exceeded")


def _imported_task(tmp_path: Path):
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
    return store.get_task(task.id)


def test_continue_imported_codex_session_prefers_app_server_thread_turn(tmp_path: Path) -> None:
    task = _imported_task(tmp_path)
    process_runner = FakeProcessRunner()
    app_server = FakeAppServerClient("App-server turn finished")
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=process_runner,
        app_server_client=app_server,
    )

    result = adapter.continue_task(task, "从钉钉继续执行")

    assert result.summary == "App-server turn finished"
    assert app_server.calls == [
        ("019e0024-4186-7440-b23b-0185fd8def85", "从钉钉继续执行", tmp_path)
    ]
    assert process_runner.calls == []


def test_continue_imported_codex_session_prefers_gui_injection(tmp_path: Path) -> None:
    task = _imported_task(tmp_path)
    process_runner = FakeProcessRunner()
    gui = FakeGuiClient("GUI handoff submitted")
    app_server = FakeAppServerClient("App-server turn finished")
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=process_runner,
        gui_client=gui,
        app_server_client=app_server,
    )

    result = adapter.continue_task(task, "从钉钉交给 GUI 执行")

    assert result.summary == "GUI handoff submitted"
    assert gui.calls == [
        ("019e0024-4186-7440-b23b-0185fd8def85", "从钉钉交给 GUI 执行", tmp_path)
    ]
    assert app_server.calls == []
    assert process_runner.calls == []


def test_continue_imported_codex_session_returns_gui_assistant_reply(tmp_path: Path) -> None:
    task = _imported_task(tmp_path)
    process_runner = FakeProcessRunner()
    gui = FakeGuiClient("GUI handoff submitted")
    session_source = FakeSessionSource("助手：GUI_POC_OK")
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=process_runner,
        gui_client=gui,
        session_source=session_source,
    )

    result = adapter.continue_task(task, "请只回复 GUI_POC_OK")

    assert result.summary == "助手：GUI_POC_OK"
    assert session_source.count_calls == ["019e0024-4186-7440-b23b-0185fd8def85"]
    assert session_source.wait_calls == [("019e0024-4186-7440-b23b-0185fd8def85", 3)]
    assert process_runner.calls == []


def test_continue_imported_codex_session_falls_back_when_gui_unavailable(tmp_path: Path) -> None:
    task = _imported_task(tmp_path)
    process_runner = FakeProcessRunner()
    gui = FailingGuiClient()
    app_server = FakeAppServerClient("App-server turn finished")
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=process_runner,
        gui_client=gui,
        app_server_client=app_server,
    )

    result = adapter.continue_task(task, "从钉钉交给 GUI 执行")

    assert result.summary == "App-server turn finished"
    assert gui.calls == [
        ("019e0024-4186-7440-b23b-0185fd8def85", "从钉钉交给 GUI 执行", tmp_path)
    ]
    assert app_server.calls == [
        ("019e0024-4186-7440-b23b-0185fd8def85", "从钉钉交给 GUI 执行", tmp_path)
    ]


def test_continue_imported_codex_session_falls_back_to_exec_resume(tmp_path: Path) -> None:
    task = _imported_task(tmp_path)
    runner = FakeProcessRunner()
    app_server = FailingAppServerClient()
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=runner,
        app_server_client=app_server,
    )

    result = adapter.continue_task(task, "从钉钉继续执行")

    assert result.summary == "Codex finished the remote instruction"
    assert app_server.calls == [
        ("019e0024-4186-7440-b23b-0185fd8def85", "从钉钉继续执行", tmp_path)
    ]
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


def test_continue_imported_codex_session_does_not_fallback_after_turn_started(
    tmp_path: Path,
) -> None:
    task = _imported_task(tmp_path)
    runner = FakeProcessRunner()
    app_server = FailedTurnAppServerClient()
    adapter = CodexAdapter(
        command="codex-test",
        process_runner=runner,
        app_server_client=app_server,
    )

    result = adapter.continue_task(task, "从钉钉继续执行")

    assert "context window exceeded" in result.summary
    assert runner.calls == []


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
