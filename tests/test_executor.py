import subprocess
from pathlib import Path

import pytest

from codex_remote_control.config import AppConfig
from codex_remote_control.executor import WorkspaceExecutor, WorkspaceNotAllowedError


def _executor_for(workspace: Path) -> WorkspaceExecutor:
    return WorkspaceExecutor(AppConfig.for_tests(workspace_roots=[workspace]))


def _git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def test_rejects_workspace_outside_whitelist(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    executor = _executor_for(allowed)

    with pytest.raises(WorkspaceNotAllowedError):
        executor.ensure_allowed(blocked)


def test_git_status_returns_short_status_from_initialized_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "new.txt").write_text("hello\n", encoding="utf-8")
    executor = _executor_for(repo)

    assert executor.git_status(repo) == "?? new.txt\n"


def test_run_command_runs_in_allowed_workspace_and_captures_stdout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    command = "python -c \"from pathlib import Path; print(Path.cwd().name)\""
    executor = _executor_for(workspace)

    result = executor.run_command(workspace, command)

    assert result.exit_code == 0
    assert result.stdout == "workspace\n"
    assert result.stderr == ""


def test_git_diff_summary_returns_stat_output_for_modified_tracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    tracked.write_text("before\nafter\n", encoding="utf-8")
    executor = _executor_for(repo)

    summary = executor.git_diff_summary(repo)

    assert "tracked.txt" in summary
    assert "1 insertion" in summary


def test_commit_creates_commit_and_returns_short_hash(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "committed.txt").write_text("content\n", encoding="utf-8")
    executor = _executor_for(repo)

    short_hash = executor.commit(repo, "add committed file")

    assert len(short_hash) >= 7
    _git(repo, "rev-parse", "--verify", f"{short_hash}^{{commit}}")
    assert executor.git_status(repo) == ""
