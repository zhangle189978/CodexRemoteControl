from datetime import UTC, datetime
from pathlib import Path

from codex_remote_control.codex_sessions import CodexSession
from codex_remote_control.config import AppConfig
from codex_remote_control.models import PermissionLevel, TaskStatus
from codex_remote_control.router import ConversationRouter
from codex_remote_control.store import TaskStore


def _router(tmp_path: Path) -> tuple[ConversationRouter, TaskStore]:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    return ConversationRouter(config, store), store


class _FakeCodexSessions:
    def __init__(self, sessions: list[CodexSession]) -> None:
        self.sessions = sessions
        self.progress_by_id: dict[str, str] = {}
        self.tail_by_id: dict[tuple[str, int], str] = {}

    def list_recent(self, limit: int = 5) -> list[CodexSession]:
        return self.sessions[:limit]

    def get_by_index(self, index: int) -> CodexSession | None:
        if index < 1 or index > len(self.sessions):
            return None
        return self.sessions[index - 1]

    def get_progress(self, session_id: str, limit: int = 12) -> str:
        return self.progress_by_id.get(session_id, "")

    def get_tail(self, session_id: str, limit: int = 20) -> str:
        return self.tail_by_id.get((session_id, limit), "")


def test_new_task_sets_current_task(tmp_path: Path) -> None:
    router, store = _router(tmp_path)
    workspace = tmp_path / "Repo"

    response = router.handle("ou_allowed", f"/新任务 {workspace} 修复索引问题")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.workspace_path == workspace.resolve()
    assert current.permission is PermissionLevel.WORK
    assert current.title == "修复索引问题"
    assert "修复索引问题" in response
    assert store.get_last_remote_user_id() == "ou_allowed"


def test_plain_text_without_current_task_prompts_new_task(tmp_path: Path) -> None:
    router, _store = _router(tmp_path)

    response = router.handle("ou_allowed", "继续写测试")

    assert "/新任务" in response


def test_plain_text_does_not_confirm_pending_action(tmp_path: Path) -> None:
    router, store = _router(tmp_path)
    task = store.create_task(
        user_id="ou_allowed",
        title="Commit work",
        workspace_path=tmp_path / "Repo",
        permission=PermissionLevel.WORK,
        goal="Commit work",
    )
    store.set_current_task("ou_allowed", task.id)
    store.set_pending_commit(task.id, "feat: commit work")

    response = router.handle("ou_allowed", "确认")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.status is TaskStatus.WAITING_CONFIRMATION
    assert current.pending_action is not None
    assert "/确认" in response


def test_status_reports_current_task_title_and_status(tmp_path: Path) -> None:
    router, store = _router(tmp_path)
    task = store.create_task(
        user_id="ou_allowed",
        title="Fix router",
        workspace_path=tmp_path / "Repo",
        permission=PermissionLevel.WORK,
        goal="Fix router",
    )
    store.set_current_task("ou_allowed", task.id)

    response = router.handle("ou_allowed", "/状态")

    assert "Fix router" in response
    assert TaskStatus.CREATED.value in response


def test_invalid_parser_result_is_surfaced_by_router(tmp_path: Path) -> None:
    router, _store = _router(tmp_path)

    response = router.handle("ou_allowed", "/切换 abc")

    assert response == "用法：/切换 <编号>"


def test_sessions_list_and_switch_work(tmp_path: Path) -> None:
    router, store = _router(tmp_path)
    workspace = tmp_path / "Repo"
    first = store.create_task(
        user_id="ou_allowed",
        title="First task",
        workspace_path=workspace,
        permission=PermissionLevel.WORK,
        goal="First task",
    )
    second = store.create_task(
        user_id="ou_allowed",
        title="Second task",
        workspace_path=workspace,
        permission=PermissionLevel.WORK,
        goal="Second task",
    )

    sessions = router.handle("ou_allowed", "/会话")
    assert "1. Second task" in sessions
    assert "2. First task" in sessions

    response = router.handle("ou_allowed", "/切换 2")

    assert "First task" in response
    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.id == first.id
    assert current.id != second.id


def test_recent_codex_sessions_lists_import_candidates(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    router = ConversationRouter(
        config,
        store,
        codex_sessions=_FakeCodexSessions(
            [
                CodexSession(
                    session_id="019e0000-aaaa-bbbb-cccc-123456789abc",
                    thread_name="Build handoff",
                    updated_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                    workspace_path=workspace,
                    summary="继续做钉钉接管",
                )
            ]
        ),
    )

    response = router.handle("ou_allowed", "/最近会话")

    assert "1. Build handoff" in response
    assert "56789abc" in response
    assert str(workspace) in response


def test_import_recent_codex_session_creates_current_task(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    router = ConversationRouter(
        config,
        store,
        codex_sessions=_FakeCodexSessions(
            [
                CodexSession(
                    session_id="019e0000-aaaa-bbbb-cccc-123456789abc",
                    thread_name="Build handoff",
                    updated_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                    workspace_path=workspace,
                    summary="继续做钉钉接管",
                )
            ]
        ),
    )

    response = router.handle("ou_allowed", "/导入最近")

    current = store.get_current_task("ou_allowed")
    assert current is not None
    assert current.title == "Build handoff"
    assert current.workspace_path == workspace
    assert "已导入 Codex 会话" in response


def test_import_recent_codex_session_rejects_unknown_index(tmp_path: Path) -> None:
    router, _store = _router(tmp_path)

    response = router.handle("ou_allowed", "/导入最近 99")

    assert response == "没有找到这个编号的 Codex 会话，请先使用 /最近会话 查看。"


def test_progress_reads_imported_codex_session(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    fake_sessions = _FakeCodexSessions(
        [
            CodexSession(
                session_id="019e0000-aaaa-bbbb-cccc-123456789abc",
                thread_name="Build handoff",
                updated_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                workspace_path=workspace,
                summary="初始摘要",
            )
        ]
    )
    fake_sessions.progress_by_id[
        "019e0000-aaaa-bbbb-cccc-123456789abc"
    ] = "助手：测试通过，等待你确认。"
    router = ConversationRouter(config, store, codex_sessions=fake_sessions)

    router.handle("ou_allowed", "/导入最近")
    response = router.handle("ou_allowed", "/进展")

    assert response == "助手：测试通过，等待你确认。"


def test_tail_reads_imported_codex_session_with_limit(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    fake_sessions = _FakeCodexSessions(
        [
            CodexSession(
                session_id="019e0000-aaaa-bbbb-cccc-123456789abc",
                thread_name="Build handoff",
                updated_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                workspace_path=workspace,
                summary="初始摘要",
            )
        ]
    )
    fake_sessions.tail_by_id[
        ("019e0000-aaaa-bbbb-cccc-123456789abc", 3)
    ] = "最近 3 条"
    router = ConversationRouter(config, store, codex_sessions=fake_sessions)

    router.handle("ou_allowed", "/导入最近")
    response = router.handle("ou_allowed", "/尾巴 3")

    assert response == "最近 3 条"


def test_refresh_updates_imported_codex_session_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config = AppConfig.for_tests(workspace_roots=[workspace])
    store = TaskStore(":memory:")
    fake_sessions = _FakeCodexSessions(
        [
            CodexSession(
                session_id="019e0000-aaaa-bbbb-cccc-123456789abc",
                thread_name="Build handoff",
                updated_at=datetime(2026, 5, 7, 9, 0, tzinfo=UTC),
                workspace_path=workspace,
                summary="初始摘要",
            )
        ]
    )
    fake_sessions.progress_by_id[
        "019e0000-aaaa-bbbb-cccc-123456789abc"
    ] = "助手：最新进展"
    router = ConversationRouter(config, store, codex_sessions=fake_sessions)

    router.handle("ou_allowed", "/导入最近")
    response = router.handle("ou_allowed", "/刷新")

    current = store.get_current_task("ou_allowed")
    assert response == "助手：最新进展"
    assert current is not None
    assert "助手：最新进展" in current.summary


def test_progress_without_imported_session_explains_next_step(tmp_path: Path) -> None:
    router, _store = _router(tmp_path)

    response = router.handle("ou_allowed", "/进展")

    assert "/导入最近" in response
