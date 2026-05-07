from pathlib import Path

import pytest

from codex_remote_control.config import AppConfig, load_config


def test_load_config_normalizes_workspace_roots(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config_file = tmp_path / "local.toml"
    workspace_text = str(workspace).replace("\\", "\\\\")
    sqlite_text = (tmp_path / "data.db").as_posix()
    config_file.write_text(
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

[dingtalk]
enabled = true
client_id = "ding_test"
client_secret = "ding_secret"
gateway_token = "ding_token"
gateway_password = ""
require_mention = false
group_policy = "open"
group_session_scope = "group"
allowed_user_ids = ["ding_user_1"]

[storage]
sqlite_path = "{sqlite_text}"

[codex]
command = "codex"

[[workspace]]
name = "Repo"
root = "{workspace_text}"
default_test_command = "pytest"
''',
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert isinstance(config, AppConfig)
    assert config.dingtalk.enabled
    assert config.dingtalk.client_id == "ding_test"
    assert config.dingtalk.gateway_token == "ding_token"
    assert not config.dingtalk.require_mention
    assert config.dingtalk.allowed_user_ids == frozenset({"ding_user_1"})
    assert config.workspace_by_name("Repo").root == workspace.resolve()
    assert config.storage.sqlite_path == (tmp_path / "data.db").resolve()
    assert config.is_allowed_workspace(workspace / "src")


def test_rejects_path_outside_workspace(tmp_path: Path) -> None:
    allowed = tmp_path / "Allowed"
    blocked = tmp_path / "Blocked"
    allowed.mkdir()
    blocked.mkdir()
    config = AppConfig.for_tests(
        allowed_user_ids=["ou_allowed"],
        workspace_roots=[allowed],
    )

    assert config.is_allowed_workspace(allowed / "file.py")
    assert config.is_allowed_workspace(allowed)
    assert not config.is_allowed_workspace(blocked / "file.py")


def test_rejects_sibling_prefix_workspace(tmp_path: Path) -> None:
    allowed = tmp_path / "Allowed"
    sibling = tmp_path / "AllowedSibling"
    allowed.mkdir()
    sibling.mkdir()
    config = AppConfig.for_tests(
        allowed_user_ids=["ou_allowed"],
        workspace_roots=[allowed],
    )

    assert not config.is_allowed_workspace(sibling / "file.py")


def test_for_tests_allows_empty_user_whitelist(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=[], workspace_roots=[tmp_path])

    assert config.feishu.allowed_user_ids == frozenset()


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml")
