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
