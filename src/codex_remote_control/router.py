from __future__ import annotations

from pathlib import Path

from codex_remote_control.codex_sessions import CodexSession, CodexSessionSource
from codex_remote_control.commands import CommandKind, parse_message
from codex_remote_control.config import AppConfig
from codex_remote_control.models import PermissionLevel, TaskStatus
from codex_remote_control.runner import TaskRunner
from codex_remote_control.store import TaskStore


class ConversationRouter:
    def __init__(
        self,
        config: AppConfig,
        store: TaskStore,
        runner: TaskRunner | None = None,
        codex_sessions: CodexSessionSource | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.runner = runner or TaskRunner(config, store)
        self.codex_sessions = codex_sessions or CodexSessionSource()

    def handle(self, user_id: str, text: str) -> str:
        self.store.record_remote_user(user_id)
        command = parse_message(text)
        match command.kind:
            case CommandKind.INVALID:
                return command.text
            case CommandKind.NEW_TASK:
                return self._new_task(user_id, command.args)
            case CommandKind.SESSIONS:
                return self._sessions(user_id)
            case CommandKind.SWITCH:
                return self._switch(user_id, int(command.args["index"]))
            case CommandKind.STATUS:
                return self.runner.status(user_id)
            case CommandKind.CONTINUE:
                current = self.store.get_current_task(user_id)
                if current and current.status is TaskStatus.WAITING_CONFIRMATION:
                    return "当前任务等待确认 release 动作，必须使用 /确认 或 /拒绝。"
                return self.runner.continue_current(user_id, command.text)
            case CommandKind.PAUSE:
                return self._pause(user_id)
            case CommandKind.CONFIRM:
                return self.runner.confirm(user_id)
            case CommandKind.REJECT:
                return self.runner.reject(user_id)
            case CommandKind.RUN_TESTS:
                return self.runner.run_tests(user_id)
            case CommandKind.DIFF:
                return self.runner.diff(user_id)
            case CommandKind.COMMIT:
                return self._prepare_commit(user_id)
            case CommandKind.RECENT_CODEX_SESSIONS:
                return self._recent_codex_sessions()
            case CommandKind.IMPORT_RECENT_CODEX_SESSION:
                return self._import_recent_codex_session(user_id, int(command.args["index"]))

    def _new_task(self, user_id: str, args: dict[str, object]) -> str:
        workspace_path = Path(str(args["workspace_path"])).resolve()
        if not self.config.is_allowed_workspace(workspace_path):
            return "项目路径不在白名单内，已拒绝执行。"
        goal = str(args["goal"])
        task = self.store.create_task(
            user_id=user_id,
            title=goal[:32] or workspace_path.name,
            workspace_path=workspace_path,
            permission=PermissionLevel.WORK,
            goal=goal,
        )
        self.store.set_current_task(user_id, task.id)
        return f"已创建任务 #{task.id}：{task.title}"

    def _sessions(self, user_id: str) -> str:
        tasks = self.store.list_tasks(user_id)
        if not tasks:
            return "暂无任务，请使用 /新任务 <项目路径> <目标>。"
        return "\n".join(
            f"{index}. {task.title} - {task.status.value}"
            for index, task in enumerate(tasks, start=1)
        )

    def _switch(self, user_id: str, index: int) -> str:
        tasks = self.store.list_tasks(user_id)
        offset = index - 1
        if offset < 0 or offset >= len(tasks):
            return "任务编号不存在。"
        task = tasks[offset]
        self.store.set_current_task(user_id, task.id)
        return f"已切换到任务 #{task.id}：{task.title}"

    def _pause(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务。"
        self.store.set_status(task.id, TaskStatus.PAUSED)
        return "已暂停当前任务。"

    def _prepare_commit(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        self.store.set_pending_commit(task.id, f"Update {task.title}")
        return "准备提交当前改动。请使用 /确认 执行 commit，或使用 /拒绝 取消。"

    def _recent_codex_sessions(self) -> str:
        sessions = self.codex_sessions.list_recent(limit=5)
        if not sessions:
            return "没有找到可导入的 Codex 会话。"
        return "\n".join(
            f"{index}. {session.thread_name} - {session.updated_at:%Y-%m-%d %H:%M} "
            f"- ...{session.short_id} - {session.workspace_path or '未知工作区'}"
            for index, session in enumerate(sessions, start=1)
        )

    def _import_recent_codex_session(self, user_id: str, index: int) -> str:
        session = self.codex_sessions.get_by_index(index)
        if session is None:
            return "没有找到这个编号的 Codex 会话，请先使用 /最近会话 查看。"
        workspace_path = self._workspace_for_session(session)
        task = self.store.create_imported_session_task(
            user_id=user_id,
            title=session.thread_name[:32],
            workspace_path=workspace_path,
            codex_session_id=session.session_id,
            summary_text=session.summary or f"接管 Codex 会话：{session.thread_name}",
        )
        return f"已导入 Codex 会话 #{task.id}：{task.title} (...{session.short_id})"

    def _workspace_for_session(self, session: CodexSession) -> Path:
        if session.workspace_path is not None:
            return session.workspace_path
        if self.config.workspaces:
            return self.config.workspaces[0].root
        return Path.cwd()
