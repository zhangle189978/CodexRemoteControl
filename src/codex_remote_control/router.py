from __future__ import annotations

from pathlib import Path

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
    ) -> None:
        self.config = config
        self.store = store
        self.runner = runner or TaskRunner(config, store)

    def handle(self, user_id: str, text: str) -> str:
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
