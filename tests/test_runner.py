import json
from pathlib import Path

from codex_remote_control.codex_adapter import CodexResult
from codex_remote_control.config import AppConfig
from codex_remote_control.executor import CommandResult, WorkspaceCommandError
from codex_remote_control.models import PermissionLevel, TaskStatus
from codex_remote_control.runner import TaskRunner
from codex_remote_control.store import TaskStore


class FakeCodex:
    def __init__(self, result: CodexResult) -> None:
        self.result = result
        self.calls: list[tuple[int, str]] = []

    def continue_task(self, task, instruction: str) -> CodexResult:
        self.calls.append((task.id, instruction))
        return self.result


class FakeExecutor:
    def __init__(self) -> None:
        self.commits: list[tuple[Path, str]] = []
        self.diff_error: Exception | None = None
        self.test_result = CommandResult(exit_code=0, stdout="tests ok\n", stderr="")
        self.commit_error: WorkspaceCommandError | None = None

    def git_diff_summary(self, workspace_path: Path) -> str:
        if self.diff_error:
            raise self.diff_error
        return f"diff for {workspace_path.name}"

    def run_command(self, workspace_path: Path, command: str) -> CommandResult:
        return self.test_result

    def commit(self, workspace_path: Path, message: str) -> str:
        if self.commit_error:
            raise self.commit_error
        self.commits.append((workspace_path, message))
        return "abc1234"


def _runner(tmp_path: Path) -> tuple[TaskRunner, TaskStore, FakeExecutor, FakeCodex]:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    executor = FakeExecutor()
    codex = FakeCodex(CodexResult(summary="Implemented request", changed=True))
    return TaskRunner(config, store, codex=codex, executor=executor), store, executor, codex


def _current_task(store: TaskStore, tmp_path: Path):
    task = store.create_task(
        user_id="ou_allowed",
        title="Fix runner",
        workspace_path=tmp_path / "Repo",
        permission=PermissionLevel.WORK,
        goal="Fix runner",
    )
    store.set_current_task("ou_allowed", task.id)
    return task


def test_continue_current_runs_codex_and_updates_status(tmp_path: Path) -> None:
    runner, store, _executor, codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)

    response = runner.continue_current("ou_allowed", "继续实现")

    assert codex.calls == [(task.id, "继续实现")]
    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.status is TaskStatus.RUNNING
    assert current.summary == "Implemented request"
    assert "Implemented request" in response


def test_continue_imported_codex_session_preserves_source_metadata(tmp_path: Path) -> None:
    runner, store, _executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    store.set_status(
        task.id,
        TaskStatus.CREATED,
        json.dumps(
            {
                "source": "codex_session",
                "codex_session_id": "019e-session",
                "summary": "用户：接管",
            }
        ),
    )

    response = runner.continue_current("ou_allowed", "继续实现")

    current = store.get_task(task.id)
    summary = json.loads(current.summary)
    assert response == "Implemented request"
    assert summary["source"] == "codex_session"
    assert summary["codex_session_id"] == "019e-session"
    assert summary["summary"] == "Implemented request"


def test_status_for_imported_codex_session_shows_readable_summary(tmp_path: Path) -> None:
    runner, store, _executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    store.set_status(
        task.id,
        TaskStatus.CREATED,
        json.dumps(
            {
                "source": "codex_session",
                "codex_session_id": "019e-session",
                "summary": "助手：可以从钉钉继续。",
            },
            ensure_ascii=False,
        ),
    )

    response = runner.status("ou_allowed")

    assert "助手：可以从钉钉继续。" in response
    assert "codex_session_id" not in response


def test_confirm_commits_pending_action_and_clears_it(tmp_path: Path) -> None:
    runner, store, executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    store.set_pending_commit(task.id, "feat: add runner")

    response = runner.confirm("ou_allowed")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.status is TaskStatus.RUNNING
    assert current.pending_action is None
    assert executor.commits == [(task.workspace_path, "feat: add runner")]
    assert "abc1234" in response


def test_confirm_failure_clears_pending_action_and_marks_failed(tmp_path: Path) -> None:
    runner, store, executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    store.set_pending_commit(task.id, "feat: add runner")
    executor.commit_error = WorkspaceCommandError(
        ["git", "commit"],
        CommandResult(exit_code=1, stdout="", stderr="nothing to commit"),
    )

    response = runner.confirm("ou_allowed")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.status is TaskStatus.FAILED
    assert current.pending_action is None
    assert "nothing to commit" in response


def test_reject_clears_pending_action_and_pauses(tmp_path: Path) -> None:
    runner, store, _executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    store.set_pending_commit(task.id, "feat: add runner")

    response = runner.reject("ou_allowed")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.status is TaskStatus.PAUSED
    assert current.pending_action is None
    assert "paused" in response.lower()


def test_diff_requires_current_task(tmp_path: Path) -> None:
    runner, _store, _executor, _codex = _runner(tmp_path)

    response = runner.diff("ou_allowed")

    assert "/新任务" in response


def test_diff_failure_marks_task_failed(tmp_path: Path) -> None:
    runner, store, executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    executor.diff_error = WorkspaceCommandError(
        ["git", "diff"],
        CommandResult(exit_code=128, stdout="", stderr="not a git repo"),
    )

    response = runner.diff("ou_allowed")

    current = store.get_task(task.id)
    assert current.status is TaskStatus.FAILED
    assert "not a git repo" in response


def test_run_tests_updates_status_from_command_result(tmp_path: Path) -> None:
    runner, store, executor, _codex = _runner(tmp_path)
    task = _current_task(store, tmp_path)
    executor.test_result = CommandResult(exit_code=1, stdout="", stderr="tests failed\n")

    response = runner.run_tests("ou_allowed")

    current = store.get_task(task.id)
    assert current.status is TaskStatus.FAILED
    assert current.summary == "tests failed"
    assert response == "tests failed"


def test_read_permission_cannot_continue_or_confirm(tmp_path: Path) -> None:
    runner, store, _executor, _codex = _runner(tmp_path)
    task = store.create_task(
        user_id="ou_allowed",
        title="Read only",
        workspace_path=tmp_path / "Repo",
        permission=PermissionLevel.READ,
        goal="Inspect only",
    )
    store.set_current_task("ou_allowed", task.id)

    assert "权限不足" in runner.continue_current("ou_allowed", "修改代码")
    store.set_pending_commit(task.id, "feat: should not commit")
    assert "权限不足" in runner.confirm("ou_allowed")
