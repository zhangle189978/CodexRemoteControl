from pathlib import Path

from codex_remote_control.models import PendingActionKind, PermissionLevel, TaskStatus
from codex_remote_control.store import TaskStore


def test_create_and_get_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")

    created = store.create_task(
        user_id="ou_user",
        title="Fix indexing",
        workspace_path=tmp_path / "Repo",
        permission=PermissionLevel.WORK,
        goal="Make index tests pass",
    )
    loaded = store.get_task(created.id)

    assert loaded == created
    assert loaded.status is TaskStatus.CREATED
    assert loaded.last_user_instruction == "Make index tests pass"
    assert loaded.summary == ""


def test_current_task_survives_reopening_store(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "nested" / "tasks.db"
    store = TaskStore(sqlite_path)
    task = store.create_task(
        user_id="ou_user",
        title="Continue work",
        workspace_path=tmp_path,
        permission=PermissionLevel.READ,
        goal="Pick this up later",
    )
    store.set_current_task("ou_user", task.id)

    reopened = TaskStore(sqlite_path)

    assert reopened.get_current_task("ou_user") == task


def test_pending_commit_round_trips_and_waits_for_confirmation(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    task = store.create_task(
        user_id="ou_user",
        title="Commit work",
        workspace_path=tmp_path,
        permission=PermissionLevel.RELEASE,
        goal="Prepare commit",
    )

    store.set_pending_commit(task.id, "feat: persist tasks")
    loaded = store.get_task(task.id)

    assert loaded.status is TaskStatus.WAITING_CONFIRMATION
    assert loaded.pending_action is not None
    assert loaded.pending_action.kind is PendingActionKind.COMMIT
    assert loaded.pending_action.payload == {"message": "feat: persist tasks"}

    store.clear_pending_action(task.id, TaskStatus.RUNNING)

    cleared = store.get_task(task.id)
    assert cleared.status is TaskStatus.RUNNING
    assert cleared.pending_action is None


def test_list_tasks_filters_by_user_and_orders_newest_updated_first(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    older = store.create_task(
        user_id="ou_user",
        title="Older",
        workspace_path=tmp_path / "older",
        permission=PermissionLevel.WORK,
        goal="First",
    )
    other_user = store.create_task(
        user_id="ou_other",
        title="Other",
        workspace_path=tmp_path / "other",
        permission=PermissionLevel.WORK,
        goal="Other",
    )
    newer = store.create_task(
        user_id="ou_user",
        title="Newer",
        workspace_path=tmp_path / "newer",
        permission=PermissionLevel.WORK,
        goal="Second",
    )
    store.set_status(older.id, TaskStatus.PAUSED, summary="bumped")

    listed = store.list_tasks("ou_user")

    assert [task.id for task in listed] == [older.id, newer.id]
    assert other_user.id not in {task.id for task in listed}


def test_get_current_task_returns_none_without_current_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")

    assert store.get_current_task("ou_unknown") is None
