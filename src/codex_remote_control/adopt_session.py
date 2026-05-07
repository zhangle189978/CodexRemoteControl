from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from codex_remote_control.codex_sessions import CodexSession, CodexSessionSource
from codex_remote_control.config import load_config
from codex_remote_control.store import TaskStore


@dataclass(frozen=True)
class AdoptResult:
    task_id: int
    user_id: str
    session_id: str
    title: str


def adopt_recent_session(
    config_path: str | Path,
    codex_home: str | Path | None = None,
    index: int = 1,
    user_id: str | None = None,
) -> AdoptResult:
    config = load_config(config_path)
    store = TaskStore(config.storage.sqlite_path)
    target_user_id = user_id or store.get_last_remote_user_id()
    if target_user_id is None:
        raise ValueError("没有最近的钉钉用户，请先在钉钉里发送任意命令，或显式传入 user id。")
    source = CodexSessionSource(codex_home)
    session = source.get_by_index(index)
    if session is None:
        raise ValueError("没有找到这个编号的 Codex 会话。")
    task = store.create_imported_session_task(
        user_id=target_user_id,
        title=session.thread_name[:32],
        workspace_path=_workspace_for_session(config.workspaces, session),
        codex_session_id=session.session_id,
        summary_text=session.summary or f"接管 Codex 会话：{session.thread_name}",
    )
    return AdoptResult(
        task_id=task.id,
        user_id=target_user_id,
        session_id=session.session_id,
        title=task.title,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a recent Codex desktop session.")
    parser.add_argument("--config", default="config/local.toml")
    parser.add_argument("--codex-home", default=None)
    parser.add_argument("--index", type=int, default=1)
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()
    result = adopt_recent_session(
        args.config,
        codex_home=args.codex_home,
        index=args.index,
        user_id=args.user_id,
    )
    print(f"已导入任务 #{result.task_id} 给 {result.user_id}：{result.title}")


def _workspace_for_session(workspaces: object, session: CodexSession) -> Path:
    if session.workspace_path is not None:
        return session.workspace_path
    workspace_tuple = tuple(workspaces) if workspaces else ()
    if workspace_tuple:
        return workspace_tuple[0].root
    return Path.cwd()


if __name__ == "__main__":
    main()
