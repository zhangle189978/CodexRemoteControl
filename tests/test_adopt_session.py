import json
from pathlib import Path

from codex_remote_control.adopt_session import adopt_recent_session
from codex_remote_control.store import TaskStore


def test_adopt_recent_session_uses_last_remote_user(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    sqlite_path = tmp_path / "tasks.db"
    config_path = tmp_path / "local.toml"
    config_path.write_text(
        f'''
[server]
host = "127.0.0.1"
port = 8765

[feishu]
app_id = "cli_test"
app_secret = "secret"
verification_token = "token"
encrypt_key = ""
allowed_user_ids = ["ou_allowed"]

[storage]
sqlite_path = "{sqlite_path.as_posix()}"

[codex]
command = "codex"

[[workspace]]
name = "Repo"
root = "{str(workspace).replace("\\", "\\\\")}"
default_test_command = "pytest"
''',
        encoding="utf-8",
    )
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "session-new",
                "thread_name": "PC handoff",
                "updated_at": "2026-05-07T02:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store = TaskStore(sqlite_path)
    store.record_remote_user("ding_user_1")

    result = adopt_recent_session(config_path, codex_home=codex_home, index=1, user_id=None)

    reopened = TaskStore(sqlite_path)
    current = reopened.get_current_task("ding_user_1")
    assert current is not None
    assert current.title == "PC handoff"
    assert result.task_id == current.id
    assert result.user_id == "ding_user_1"
