from __future__ import annotations

from codex_remote_control.codex_adapter import CodexAdapter
from codex_remote_control.config import AppConfig
from codex_remote_control.executor import WorkspaceCommandError, WorkspaceExecutor
from codex_remote_control.models import PendingActionKind, TaskStatus
from codex_remote_control.store import TaskStore


class TaskRunner:
    def __init__(
        self,
        config: AppConfig,
        store: TaskStore,
        codex: CodexAdapter | None = None,
        executor: WorkspaceExecutor | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.codex = codex or CodexAdapter()
        self.executor = executor or WorkspaceExecutor(config)

    def status(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        detail = task.summary or task.last_user_instruction
        return f"{task.title} - {task.status.value}\n{detail}"

    def continue_current(self, user_id: str, instruction: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        if task.status is TaskStatus.WAITING_CONFIRMATION:
            return "当前任务等待确认 release 动作，必须使用 /确认 或 /拒绝。"
        result = self.codex.continue_task(task, instruction)
        self.store.set_status(task.id, TaskStatus.RUNNING, result.summary)
        return result.summary

    def diff(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        summary = self.executor.git_diff_summary(task.workspace_path)
        return summary or "当前没有 diff。"

    def run_tests(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        workspace = self._workspace_for_task(task.workspace_path)
        result = self.executor.run_command(task.workspace_path, workspace.default_test_command)
        output = (result.stdout + result.stderr).strip()
        status = TaskStatus.RUNNING if result.exit_code == 0 else TaskStatus.FAILED
        summary = output or f"测试命令退出码：{result.exit_code}"
        self.store.set_status(task.id, status, summary)
        return summary

    def confirm(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None or task.pending_action is None:
            return "没有等待确认的动作。"
        if task.pending_action.kind is not PendingActionKind.COMMIT:
            return "未知确认动作，已拒绝执行。"
        try:
            commit_hash = self.executor.commit(
                task.workspace_path,
                task.pending_action.payload["message"],
            )
        except WorkspaceCommandError as error:
            detail = error.result.stderr.strip() or error.result.stdout.strip() or str(error)
            self.store.set_status(task.id, TaskStatus.FAILED, detail)
            return f"提交失败：{detail}"
        self.store.clear_pending_action(task.id, TaskStatus.RUNNING)
        return f"已提交：{commit_hash}"

    def reject(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None or task.pending_action is None:
            return "没有等待确认的动作。"
        self.store.clear_pending_action(task.id, TaskStatus.PAUSED)
        return "Release action rejected and task paused."

    def _workspace_for_task(self, workspace_path):
        resolved = workspace_path.resolve()
        for workspace in self.config.workspaces:
            if resolved.is_relative_to(workspace.root):
                return workspace
        raise KeyError(workspace_path)
