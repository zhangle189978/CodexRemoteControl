import json
from datetime import datetime
from pathlib import Path

from codex_remote_control.codex_sessions import CodexSessionSource


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_lists_recent_codex_sessions_with_workspace_and_summary(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "session-old",
                        "thread_name": "Old work",
                        "updated_at": "2026-05-07T01:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "id": "session-new",
                        "thread_name": "Build handoff",
                        "updated_at": "2026-05-07T02:00:00Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "07" / "rollout-session-new.jsonl",
        [
            {
                "type": "session_meta",
                "payload": {"id": "session-new", "cwd": str(tmp_path / "Repo")},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "继续做钉钉接管"}],
                },
            },
        ],
    )

    sessions = CodexSessionSource(codex_home).list_recent(limit=1)

    assert len(sessions) == 1
    assert sessions[0].session_id == "session-new"
    assert sessions[0].thread_name == "Build handoff"
    assert sessions[0].workspace_path == tmp_path / "Repo"
    assert sessions[0].summary == "用户：继续做钉钉接管"


def test_summary_includes_recent_user_and_assistant_messages(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-new",
                "thread_name": "Build handoff",
                "updated_at": "2026-05-07T02:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "07" / "rollout-session-new.jsonl",
        [
            {
                "type": "session_meta",
                "payload": {"id": "session-new", "cwd": str(tmp_path / "Repo")},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "怎么切换会话？"}],
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "使用 /导入最近 1。"}],
                },
            },
        ],
    )

    session = CodexSessionSource(codex_home).list_recent(limit=1)[0]

    assert "用户：怎么切换会话？" in session.summary
    assert "助手：使用 /导入最近 1。" in session.summary


def test_get_progress_includes_recent_messages_and_tool_outputs(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "08" / "rollout-session-progress.jsonl",
        [
            {
                "timestamp": "2026-05-08T01:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-progress", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-08T01:01:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "继续实现进展查看"}],
                },
            },
            {
                "timestamp": "2026-05-08T01:02:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "exec_command_end",
                    "command": ["pytest", "-q"],
                    "exit_code": 0,
                    "aggregated_output": "80 passed in 4.09s",
                },
            },
            {
                "timestamp": "2026-05-08T01:03:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "测试通过，等待你确认提交。"}],
                },
            },
        ],
    )

    progress = CodexSessionSource(codex_home).get_progress("session-progress", limit=5)

    assert "用户：继续实现进展查看" in progress
    assert "命令完成：pytest -q -> 0" in progress
    assert "80 passed" in progress
    assert "助手：测试通过，等待你确认提交。" in progress


def test_get_progress_includes_codex_error_events(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "08" / "rollout-session-error.jsonl",
        [
            {
                "timestamp": "2026-05-08T01:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-error", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-08T01:01:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "error",
                    "message": "Codex ran out of room in the model's context window.",
                },
            },
        ],
    )

    progress = CodexSessionSource(codex_home).get_progress("session-error", limit=5)

    assert "Codex error: Codex ran out of room" in progress


def test_wait_for_next_assistant_reply_returns_task_complete_message(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "08" / "rollout-session-wait.jsonl",
        [
            {
                "timestamp": "2026-05-08T01:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-wait", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-08T01:01:00Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": "我先看一下。"},
            },
            {
                "timestamp": "2026-05-08T01:02:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "last_agent_message": "最终结论：当前分支干净。",
                },
            },
        ],
    )

    reply = CodexSessionSource(codex_home).wait_for_next_assistant_reply(
        "session-wait",
        after_event_count=0,
        timeout=0,
    )

    assert reply == "助手：最终结论：当前分支干净。"


def test_wait_for_next_assistant_reply_falls_back_to_latest_assistant_on_timeout(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "08" / "rollout-session-timeout.jsonl",
        [
            {
                "timestamp": "2026-05-08T01:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-timeout", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-08T01:01:00Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": "仍在处理。"},
            },
        ],
    )

    reply = CodexSessionSource(codex_home).wait_for_next_assistant_reply(
        "session-timeout",
        after_event_count=0,
        timeout=0,
    )

    assert reply == "助手：仍在处理。"


def test_get_tail_limits_recent_key_events(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "08" / "rollout-session-tail.jsonl",
        [
            {
                "timestamp": "2026-05-08T01:00:00Z",
                "type": "session_meta",
                "payload": {"id": "session-tail", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-08T01:01:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "第一条"}],
                },
            },
            {
                "timestamp": "2026-05-08T01:02:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "第二条"}],
                },
            },
            {
                "timestamp": "2026-05-08T01:03:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "第三条"}],
                },
            },
        ],
    )

    tail = CodexSessionSource(codex_home).get_tail("session-tail", limit=2)

    assert "第一条" not in tail
    assert "助手：第二条" in tail
    assert "用户：第三条" in tail


def test_get_by_index_uses_one_based_recent_order(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {"id": "first", "thread_name": "First", "updated_at": "2026-05-07T01:00:00Z"}
                ),
                json.dumps(
                    {"id": "second", "thread_name": "Second", "updated_at": "2026-05-07T02:00:00Z"}
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    source = CodexSessionSource(codex_home)

    assert source.get_by_index(1).session_id == "second"
    assert source.get_by_index(2).session_id == "first"
    assert source.get_by_index(3) is None


def test_list_recent_includes_active_rollout_when_index_is_stale(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "indexed-old",
                "thread_name": "Indexed old",
                "updated_at": "2026-05-07T01:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "07" / "rollout-active-new.jsonl",
        [
            {
                "timestamp": "2026-05-07T02:00:00Z",
                "type": "session_meta",
                "payload": {"id": "active-new", "cwd": str(tmp_path / "ActiveRepo")},
            },
            {
                "timestamp": "2026-05-07T02:01:00Z",
                "type": "event_msg",
                "payload": {"type": "thread_name_updated", "thread_name": "Active handoff"},
            },
        ],
    )

    sessions = CodexSessionSource(codex_home).list_recent(limit=2)

    assert [session.session_id for session in sessions] == ["active-new", "indexed-old"]
    assert sessions[0].thread_name == "Active handoff"


def test_list_recent_prefers_newer_rollout_for_indexed_session(tmp_path: Path) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "same-session",
                "thread_name": "Indexed stale name",
                "updated_at": "2026-05-07T01:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        codex_home / "sessions" / "2026" / "05" / "07" / "rollout-same-session.jsonl",
        [
            {
                "timestamp": "2026-05-07T03:00:00Z",
                "type": "session_meta",
                "payload": {"id": "same-session", "cwd": str(tmp_path / "Repo")},
            },
            {
                "timestamp": "2026-05-07T03:01:00Z",
                "type": "event_msg",
                "payload": {"type": "thread_name_updated", "thread_name": "Rollout fresh name"},
            },
        ],
    )

    session = CodexSessionSource(codex_home).list_recent(limit=1)[0]

    assert session.session_id == "same-session"
    assert session.thread_name == "Rollout fresh name"
    assert session.updated_at == datetime.fromisoformat("2026-05-07T03:01:00+00:00")
