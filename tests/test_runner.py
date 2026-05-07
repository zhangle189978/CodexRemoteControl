from pathlib import Path

from codex_remote_control.codex_adapter import CodexResult
from codex_remote_control.config import AppConfig
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

    def git_diff_summary(self, workspace_path: Path) -> str:
        return f"diff for {workspace_path.name}"

    def commit(self, workspace_path: Path, message: str) -> str:
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
