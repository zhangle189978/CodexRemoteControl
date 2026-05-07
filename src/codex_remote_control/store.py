from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from codex_remote_control.models import (
    PendingAction,
    PendingActionKind,
    PermissionLevel,
    Task,
    TaskStatus,
    now_utc,
)


class TaskStore:
    def __init__(self, sqlite_path: str | Path) -> None:
        self.sqlite_path = sqlite_path
        if sqlite_path != ":memory:":
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(sqlite_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def create_task(
        self,
        user_id: str,
        title: str,
        workspace_path: str | Path,
        permission: PermissionLevel,
        goal: str,
    ) -> Task:
        timestamp = now_utc().isoformat()
        cursor = self._connection.execute(
            """
            INSERT INTO tasks (
                user_id,
                title,
                workspace_path,
                permission,
                status,
                summary,
                last_user_instruction,
                pending_action,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                title,
                str(Path(workspace_path)),
                permission.value,
                TaskStatus.CREATED.value,
                "",
                goal,
                None,
                timestamp,
                timestamp,
            ),
        )
        self._connection.commit()
        return self.get_task(int(cursor.lastrowid))

    def create_imported_session_task(
        self,
        user_id: str,
        title: str,
        workspace_path: str | Path,
        codex_session_id: str,
        summary_text: str,
    ) -> Task:
        summary = json.dumps(
            {
                "source": "codex_session",
                "codex_session_id": codex_session_id,
                "summary": summary_text,
            },
            ensure_ascii=False,
        )
        task = self.create_task(
            user_id=user_id,
            title=title,
            workspace_path=workspace_path,
            permission=PermissionLevel.WORK,
            goal=summary_text,
        )
        self.set_status(task.id, TaskStatus.CREATED, summary=summary)
        self.set_current_task(user_id, task.id)
        return self.get_task(task.id)

    def get_task(self, task_id: int) -> Task:
        row = self._connection.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return self._row_to_task(row)

    def list_tasks(self, user_id: str) -> list[Task]:
        rows = self._connection.execute(
            """
            SELECT *
            FROM tasks
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def set_current_task(self, user_id: str, task_id: int) -> None:
        self.get_task(task_id)
        self._connection.execute(
            """
            INSERT INTO current_tasks (user_id, task_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET task_id = excluded.task_id
            """,
            (user_id, task_id),
        )
        self._connection.commit()

    def get_current_task(self, user_id: str) -> Task | None:
        row = self._connection.execute(
            "SELECT task_id FROM current_tasks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self.get_task(int(row["task_id"]))

    def record_remote_user(self, user_id: str) -> None:
        self._connection.execute(
            """
            INSERT INTO remote_users (user_id, last_seen_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
            """,
            (user_id, now_utc().isoformat()),
        )
        self._connection.commit()

    def get_last_remote_user_id(self) -> str | None:
        row = self._connection.execute(
            """
            SELECT user_id
            FROM remote_users
            ORDER BY last_seen_at DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return str(row["user_id"])

    def set_status(self, task_id: int, status: TaskStatus, summary: str | None = None) -> None:
        timestamp = now_utc().isoformat()
        if summary is None:
            cursor = self._connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, timestamp, task_id),
            )
        else:
            cursor = self._connection.execute(
                "UPDATE tasks SET status = ?, summary = ?, updated_at = ? WHERE id = ?",
                (status.value, summary, timestamp, task_id),
            )
        self._connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(task_id)

    def set_pending_commit(self, task_id: int, message: str) -> None:
        timestamp = now_utc().isoformat()
        pending_action = {
            "kind": PendingActionKind.COMMIT.value,
            "payload": {"message": message},
            "created_at": timestamp,
        }
        cursor = self._connection.execute(
            """
            UPDATE tasks
            SET status = ?, pending_action = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                TaskStatus.WAITING_CONFIRMATION.value,
                json.dumps(pending_action),
                timestamp,
                task_id,
            ),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(task_id)

    def clear_pending_action(self, task_id: int, status: TaskStatus) -> None:
        cursor = self._connection.execute(
            """
            UPDATE tasks
            SET status = ?, pending_action = NULL, updated_at = ?
            WHERE id = ?
            """,
            (status.value, now_utc().isoformat(), task_id),
        )
        self._connection.commit()
        if cursor.rowcount == 0:
            raise KeyError(task_id)

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                permission TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                last_user_instruction TEXT NOT NULL,
                pending_action TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS current_tasks (
                user_id TEXT PRIMARY KEY,
                task_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS remote_users (
                user_id TEXT PRIMARY KEY,
                last_seen_at TEXT NOT NULL
            );
            """
        )
        self._connection.commit()

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=int(row["id"]),
            user_id=str(row["user_id"]),
            title=str(row["title"]),
            workspace_path=Path(str(row["workspace_path"])),
            permission=PermissionLevel(str(row["permission"])),
            status=TaskStatus(str(row["status"])),
            summary=str(row["summary"]),
            last_user_instruction=str(row["last_user_instruction"]),
            pending_action=self._pending_action_from_json(row["pending_action"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def _pending_action_from_json(self, raw_pending_action: str | None) -> PendingAction | None:
        if raw_pending_action is None:
            return None
        pending_action = json.loads(raw_pending_action)
        return PendingAction(
            kind=PendingActionKind(str(pending_action["kind"])),
            payload=dict(pending_action["payload"]),
            created_at=datetime.fromisoformat(str(pending_action["created_at"])),
        )
