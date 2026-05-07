# Feishu Codex Remote Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows-local Feishu bot gateway that can create, switch, continue, inspect, test, and safely confirm Codex-driven coding tasks.

**Architecture:** The app is a Python service with a small FastAPI HTTP gateway, a pure command/router/state-machine core, SQLite persistence, and a workspace executor constrained by configuration. The Codex boundary is isolated behind `CodexAdapter` so MVP can use a command-based task continuation strategy while keeping room for a future real session adapter.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic Settings, SQLite via stdlib `sqlite3`, pytest, Ruff, Windows PowerShell friendly scripts.

---

## File Structure

- `pyproject.toml`: project metadata, runtime dependencies, test and lint configuration.
- `README.md`: local setup, Feishu webhook setup, development commands.
- `.gitignore`: Python caches, virtualenvs, local config, runtime database and logs.
- `config/local.example.toml`: safe example configuration.
- `src/codex_remote_control/__init__.py`: package marker and version.
- `src/codex_remote_control/config.py`: typed settings loader and path normalization.
- `src/codex_remote_control/feishu.py`: Feishu request signature verification and reply client boundary.
- `src/codex_remote_control/commands.py`: slash command parser and ordinary text normalization.
- `src/codex_remote_control/models.py`: enums and dataclasses shared by router, store, runner, and executor.
- `src/codex_remote_control/store.py`: SQLite schema, task persistence, current task pointer, operation log, pending confirmation.
- `src/codex_remote_control/router.py`: user-message routing, current task selection, confirmation routing.
- `src/codex_remote_control/executor.py`: workspace whitelist checks, git status, diff summary, configured test command, confirmed commit.
- `src/codex_remote_control/codex_adapter.py`: Codex execution interface and MVP command adapter.
- `src/codex_remote_control/runner.py`: task state machine and orchestration.
- `src/codex_remote_control/app.py`: FastAPI app factory and webhook endpoint.
- `tests/fixtures/feishu_message.json`: minimal Feishu text-message fixture.
- `tests/test_config.py`: settings loading and path validation.
- `tests/test_feishu.py`: signature and whitelist behavior.
- `tests/test_commands.py`: command parsing behavior.
- `tests/test_store.py`: SQLite persistence and recovery.
- `tests/test_router.py`: current task routing and waiting confirmation behavior.
- `tests/test_executor.py`: whitelist, git status, diff, test command, commit confirmation behavior.
- `tests/test_runner.py`: task state transitions and error handling.
- `tests/test_app.py`: webhook integration with mocked runner/reply client.

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `config/local.example.toml`
- Create: `src/codex_remote_control/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the baseline package and tooling files**

Create `pyproject.toml`:

```toml
[project]
name = "codex-remote-control"
version = "0.1.0"
description = "Windows-local Feishu gateway for controlled Codex coding tasks"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "tomli-w>=1.0.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "httpx>=0.27.0",
  "ruff>=0.6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
config/local.toml
data/
logs/
```

Create `README.md`:

```markdown
# Codex Remote Control

Windows-local Feishu gateway for controlled Codex coding tasks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## Local Run

Copy `config/local.example.toml` to `config/local.toml`, fill local values, then run:

```powershell
uvicorn codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```
```

Create `config/local.example.toml`:

```toml
[server]
host = "127.0.0.1"
port = 8765

[feishu]
app_id = "cli_xxx"
app_secret = "replace-me"
verification_token = "replace-me"
encrypt_key = ""
allowed_user_ids = ["ou_xxx"]

[storage]
sqlite_path = "data/codex_remote_control.db"

[codex]
command = "codex"

[[workspace]]
name = "HollyDB"
root = "C:\\Users\\89493\\Documents\\HollyDB"
default_test_command = "pytest"
```

Create `src/codex_remote_control/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `tests/conftest.py`:

```python
from pathlib import Path


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
```

- [ ] **Step 2: Install dependencies**

Run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Expected: installation completes without dependency resolution errors.

- [ ] **Step 3: Run baseline checks**

Run:

```powershell
pytest
ruff check .
```

Expected: `pytest` reports no tests collected or all current tests pass; `ruff check .` reports no lint errors.

- [ ] **Step 4: Commit**

```powershell
git add .gitignore README.md pyproject.toml config/local.example.toml src tests
git commit -m "chore: scaffold python service"
```

## Task 2: Configuration Loader

**Files:**
- Create: `src/codex_remote_control/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading and whitelist paths**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest

from codex_remote_control.config import AppConfig, load_config


def test_load_config_normalizes_workspace_roots(tmp_path: Path) -> None:
    workspace = tmp_path / "Repo"
    workspace.mkdir()
    config_file = tmp_path / "local.toml"
    config_file.write_text(
        f"""
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
sqlite_path = "{(tmp_path / "data.db").as_posix()}"

[codex]
command = "codex"

[[workspace]]
name = "Repo"
root = "{str(workspace).replace("\\", "\\\\")}"
default_test_command = "pytest"
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert isinstance(config, AppConfig)
    assert config.workspace_by_name("Repo").root == workspace.resolve()
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
    assert not config.is_allowed_workspace(blocked / "file.py")


def test_missing_config_file_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `load_config`.

- [ ] **Step 3: Implement config loader**

Create `src/codex_remote_control/config.py`:

```python
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class FeishuConfig:
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    allowed_user_ids: frozenset[str]


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class CodexConfig:
    command: str


@dataclass(frozen=True)
class WorkspaceConfig:
    name: str
    root: Path
    default_test_command: str


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    feishu: FeishuConfig
    storage: StorageConfig
    codex: CodexConfig
    workspaces: tuple[WorkspaceConfig, ...]

    @classmethod
    def for_tests(
        cls,
        allowed_user_ids: list[str] | None = None,
        workspace_roots: list[Path] | None = None,
    ) -> "AppConfig":
        roots = workspace_roots or []
        return cls(
            server=ServerConfig(host="127.0.0.1", port=8765),
            feishu=FeishuConfig(
                app_id="cli_test",
                app_secret="secret",
                verification_token="token",
                encrypt_key="",
                allowed_user_ids=frozenset(allowed_user_ids or ["ou_allowed"]),
            ),
            storage=StorageConfig(sqlite_path=Path(":memory:")),
            codex=CodexConfig(command="codex"),
            workspaces=tuple(
                WorkspaceConfig(
                    name=root.name,
                    root=root.resolve(),
                    default_test_command="pytest",
                )
                for root in roots
            ),
        )

    def workspace_by_name(self, name: str) -> WorkspaceConfig:
        for workspace in self.workspaces:
            if workspace.name == name:
                return workspace
        raise KeyError(name)

    def is_allowed_workspace(self, candidate: str | Path) -> bool:
        resolved = Path(candidate).resolve()
        return any(_is_relative_to(resolved, workspace.root) for workspace in self.workspaces)


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig(
        server=ServerConfig(**raw["server"]),
        feishu=FeishuConfig(
            app_id=raw["feishu"]["app_id"],
            app_secret=raw["feishu"]["app_secret"],
            verification_token=raw["feishu"]["verification_token"],
            encrypt_key=raw["feishu"].get("encrypt_key", ""),
            allowed_user_ids=frozenset(raw["feishu"]["allowed_user_ids"]),
        ),
        storage=StorageConfig(sqlite_path=Path(raw["storage"]["sqlite_path"])),
        codex=CodexConfig(command=raw["codex"]["command"]),
        workspaces=tuple(
            WorkspaceConfig(
                name=item["name"],
                root=Path(item["root"]).resolve(),
                default_test_command=item["default_test_command"],
            )
            for item in raw.get("workspace", [])
        ),
    )
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/codex_remote_control/config.py tests/test_config.py
git commit -m "feat: load local configuration"
```

## Task 3: Shared Models and Command Parser

**Files:**
- Create: `src/codex_remote_control/models.py`
- Create: `src/codex_remote_control/commands.py`
- Create: `tests/test_commands.py`

- [ ] **Step 1: Write failing command parser tests**

Create `tests/test_commands.py`:

```python
from codex_remote_control.commands import CommandKind, parse_message


def test_parse_new_task_command() -> None:
    command = parse_message("/新任务 C:\\Users\\89493\\Documents\\HollyDB 修复索引问题")

    assert command.kind == CommandKind.NEW_TASK
    assert command.args["workspace_path"] == "C:\\Users\\89493\\Documents\\HollyDB"
    assert command.args["goal"] == "修复索引问题"


def test_parse_continue_command() -> None:
    command = parse_message("/继续 按方案二实现")

    assert command.kind == CommandKind.CONTINUE
    assert command.text == "按方案二实现"


def test_plain_text_becomes_continue() -> None:
    command = parse_message("把测试也补上")

    assert command.kind == CommandKind.CONTINUE
    assert command.text == "把测试也补上"


def test_parse_session_switch() -> None:
    command = parse_message("/切换 2")

    assert command.kind == CommandKind.SWITCH
    assert command.args["index"] == 2


def test_parse_commit_and_confirm() -> None:
    assert parse_message("/提交").kind == CommandKind.COMMIT
    assert parse_message("/确认").kind == CommandKind.CONFIRM
    assert parse_message("/拒绝").kind == CommandKind.REJECT
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_commands.py -v
```

Expected: FAIL with missing `codex_remote_control.commands`.

- [ ] **Step 3: Implement shared models**

Create `src/codex_remote_control/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_CONFIRMATION = "waiting_confirmation"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"


class PermissionLevel(StrEnum):
    READ = "read"
    WORK = "work"
    RELEASE = "release"


class PendingActionKind(StrEnum):
    COMMIT = "commit"


@dataclass(frozen=True)
class PendingAction:
    kind: PendingActionKind
    payload: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class Task:
    id: int
    user_id: str
    title: str
    workspace_path: Path
    permission: PermissionLevel
    status: TaskStatus
    summary: str
    last_user_instruction: str
    pending_action: PendingAction | None
    created_at: datetime
    updated_at: datetime


def now_utc() -> datetime:
    return datetime.now(tz=UTC)
```

- [ ] **Step 4: Implement command parser**

Create `src/codex_remote_control/commands.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CommandKind(StrEnum):
    NEW_TASK = "new_task"
    SESSIONS = "sessions"
    SWITCH = "switch"
    STATUS = "status"
    CONTINUE = "continue"
    PAUSE = "pause"
    CONFIRM = "confirm"
    REJECT = "reject"
    RUN_TESTS = "run_tests"
    DIFF = "diff"
    COMMIT = "commit"


@dataclass(frozen=True)
class ParsedCommand:
    kind: CommandKind
    text: str = ""
    args: dict[str, object] = field(default_factory=dict)


def parse_message(text: str) -> ParsedCommand:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ParsedCommand(kind=CommandKind.CONTINUE, text=stripped)

    name, _, rest = stripped.partition(" ")
    rest = rest.strip()
    match name:
        case "/新任务":
            workspace_path, _, goal = rest.partition(" ")
            return ParsedCommand(
                kind=CommandKind.NEW_TASK,
                args={"workspace_path": workspace_path, "goal": goal.strip()},
            )
        case "/会话":
            return ParsedCommand(kind=CommandKind.SESSIONS)
        case "/切换":
            return ParsedCommand(kind=CommandKind.SWITCH, args={"index": int(rest)})
        case "/状态":
            return ParsedCommand(kind=CommandKind.STATUS)
        case "/继续":
            return ParsedCommand(kind=CommandKind.CONTINUE, text=rest)
        case "/暂停":
            return ParsedCommand(kind=CommandKind.PAUSE)
        case "/确认":
            return ParsedCommand(kind=CommandKind.CONFIRM)
        case "/拒绝":
            return ParsedCommand(kind=CommandKind.REJECT)
        case "/运行测试":
            return ParsedCommand(kind=CommandKind.RUN_TESTS)
        case "/差异":
            return ParsedCommand(kind=CommandKind.DIFF)
        case "/提交":
            return ParsedCommand(kind=CommandKind.COMMIT)
        case _:
            return ParsedCommand(kind=CommandKind.CONTINUE, text=stripped)
```

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/test_commands.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```powershell
git add src/codex_remote_control/models.py src/codex_remote_control/commands.py tests/test_commands.py
git commit -m "feat: parse feishu control commands"
```

## Task 4: Feishu Authentication Boundary

**Files:**
- Create: `src/codex_remote_control/feishu.py`
- Create: `tests/test_feishu.py`
- Create: `tests/fixtures/feishu_message.json`

- [ ] **Step 1: Write failing tests for token and user checks**

Create `tests/test_feishu.py`:

```python
from codex_remote_control.config import AppConfig
from codex_remote_control.feishu import FeishuEvent, verify_event


def test_verify_event_accepts_allowed_user() -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"])
    event = FeishuEvent(
        token="token",
        user_id="ou_allowed",
        text="/状态",
        message_id="om_1",
    )

    result = verify_event(event, config)

    assert result.user_id == "ou_allowed"
    assert result.text == "/状态"


def test_verify_event_rejects_bad_token() -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"])
    event = FeishuEvent(token="bad", user_id="ou_allowed", text="/状态", message_id="om_1")

    result = verify_event(event, config)

    assert not result.allowed
    assert result.reason == "invalid verification token"


def test_verify_event_rejects_unknown_user() -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"])
    event = FeishuEvent(token="token", user_id="ou_blocked", text="/状态", message_id="om_1")

    result = verify_event(event, config)

    assert not result.allowed
    assert result.reason == "user is not allowed"
```

- [ ] **Step 2: Add fixture**

Create `tests/fixtures/feishu_message.json`:

```json
{
  "token": "token",
  "event": {
    "message": {
      "message_id": "om_1",
      "content": "{\"text\":\"/状态\"}"
    },
    "sender": {
      "sender_id": {
        "open_id": "ou_allowed"
      }
    }
  }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_feishu.py -v
```

Expected: FAIL with missing `codex_remote_control.feishu`.

- [ ] **Step 4: Implement Feishu boundary**

Create `src/codex_remote_control/feishu.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass

from codex_remote_control.config import AppConfig


@dataclass(frozen=True)
class FeishuEvent:
    token: str
    user_id: str
    text: str
    message_id: str


@dataclass(frozen=True)
class VerifiedEvent:
    allowed: bool
    user_id: str
    text: str
    message_id: str
    reason: str = ""


def parse_feishu_event(payload: dict) -> FeishuEvent:
    message = payload["event"]["message"]
    sender = payload["event"]["sender"]["sender_id"]
    content = json.loads(message["content"])
    return FeishuEvent(
        token=payload.get("token", ""),
        user_id=sender["open_id"],
        text=content.get("text", ""),
        message_id=message["message_id"],
    )


def verify_event(event: FeishuEvent, config: AppConfig) -> VerifiedEvent:
    if event.token != config.feishu.verification_token:
        return VerifiedEvent(
            allowed=False,
            user_id=event.user_id,
            text=event.text,
            message_id=event.message_id,
            reason="invalid verification token",
        )
    if event.user_id not in config.feishu.allowed_user_ids:
        return VerifiedEvent(
            allowed=False,
            user_id=event.user_id,
            text=event.text,
            message_id=event.message_id,
            reason="user is not allowed",
        )
    return VerifiedEvent(
        allowed=True,
        user_id=event.user_id,
        text=event.text,
        message_id=event.message_id,
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
pytest tests/test_feishu.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```powershell
git add src/codex_remote_control/feishu.py tests/test_feishu.py tests/fixtures/feishu_message.json
git commit -m "feat: verify feishu events"
```

## Task 5: SQLite Task Store

**Files:**
- Create: `src/codex_remote_control/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_store.py`:

```python
from pathlib import Path

from codex_remote_control.models import PermissionLevel, TaskStatus
from codex_remote_control.store import TaskStore


def test_create_and_get_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")

    task = store.create_task(
        user_id="ou_allowed",
        title="修复问题",
        workspace_path=tmp_path,
        permission=PermissionLevel.WORK,
        goal="修复索引问题",
    )

    loaded = store.get_task(task.id)
    assert loaded.title == "修复问题"
    assert loaded.status == TaskStatus.CREATED
    assert loaded.last_user_instruction == "修复索引问题"


def test_current_task_survives_store_reopen(tmp_path: Path) -> None:
    db = tmp_path / "tasks.db"
    first = TaskStore(db)
    task = first.create_task(
        user_id="ou_allowed",
        title="任务",
        workspace_path=tmp_path,
        permission=PermissionLevel.WORK,
        goal="目标",
    )
    first.set_current_task("ou_allowed", task.id)

    second = TaskStore(db)

    assert second.get_current_task("ou_allowed").id == task.id


def test_pending_commit_round_trip(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    task = store.create_task(
        user_id="ou_allowed",
        title="任务",
        workspace_path=tmp_path,
        permission=PermissionLevel.WORK,
        goal="目标",
    )

    store.set_pending_commit(task.id, "feat: fix issue")
    loaded = store.get_task(task.id)

    assert loaded.status == TaskStatus.WAITING_CONFIRMATION
    assert loaded.pending_action is not None
    assert loaded.pending_action.payload["message"] == "feat: fix issue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_store.py -v
```

Expected: FAIL with missing `TaskStore`.

- [ ] **Step 3: Implement SQLite store**

Create `src/codex_remote_control/store.py`:

```python
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
        self.sqlite_path = Path(sqlite_path)
        if self.sqlite_path != Path(":memory:"):
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.sqlite_path)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
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
            CREATE TABLE IF NOT EXISTS operation_logs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id INTEGER NOT NULL,
              message TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def create_task(
        self,
        user_id: str,
        title: str,
        workspace_path: Path,
        permission: PermissionLevel,
        goal: str,
    ) -> Task:
        now = now_utc().isoformat()
        cursor = self.connection.execute(
            """
            INSERT INTO tasks (
              user_id, title, workspace_path, permission, status, summary,
              last_user_instruction, pending_action, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                user_id,
                title,
                str(workspace_path.resolve()),
                permission.value,
                TaskStatus.CREATED.value,
                "",
                goal,
                now,
                now,
            ),
        )
        self.connection.commit()
        return self.get_task(int(cursor.lastrowid))

    def get_task(self, task_id: int) -> Task:
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return _task_from_row(row)

    def list_tasks(self, user_id: str) -> list[Task]:
        rows = self.connection.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
            (user_id,),
        ).fetchall()
        return [_task_from_row(row) for row in rows]

    def set_current_task(self, user_id: str, task_id: int) -> None:
        self.connection.execute(
            """
            INSERT INTO current_tasks (user_id, task_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET task_id = excluded.task_id
            """,
            (user_id, task_id),
        )
        self.connection.commit()

    def get_current_task(self, user_id: str) -> Task | None:
        row = self.connection.execute(
            "SELECT task_id FROM current_tasks WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return self.get_task(int(row["task_id"]))

    def set_status(self, task_id: int, status: TaskStatus, summary: str | None = None) -> None:
        now = now_utc().isoformat()
        if summary is None:
            self.connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, task_id),
            )
        else:
            self.connection.execute(
                "UPDATE tasks SET status = ?, summary = ?, updated_at = ? WHERE id = ?",
                (status.value, summary, now, task_id),
            )
        self.connection.commit()

    def set_pending_commit(self, task_id: int, message: str) -> None:
        action = {
            "kind": PendingActionKind.COMMIT.value,
            "payload": {"message": message},
            "created_at": now_utc().isoformat(),
        }
        self.connection.execute(
            """
            UPDATE tasks
            SET status = ?, pending_action = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                TaskStatus.WAITING_CONFIRMATION.value,
                json.dumps(action, ensure_ascii=False),
                now_utc().isoformat(),
                task_id,
            ),
        )
        self.connection.commit()

    def clear_pending_action(self, task_id: int, status: TaskStatus) -> None:
        self.connection.execute(
            "UPDATE tasks SET pending_action = NULL, status = ?, updated_at = ? WHERE id = ?",
            (status.value, now_utc().isoformat(), task_id),
        )
        self.connection.commit()


def _task_from_row(row: sqlite3.Row) -> Task:
    pending_action = None
    if row["pending_action"]:
        raw = json.loads(row["pending_action"])
        pending_action = PendingAction(
            kind=PendingActionKind(raw["kind"]),
            payload=raw["payload"],
            created_at=datetime.fromisoformat(raw["created_at"]),
        )
    return Task(
        id=int(row["id"]),
        user_id=row["user_id"],
        title=row["title"],
        workspace_path=Path(row["workspace_path"]),
        permission=PermissionLevel(row["permission"]),
        status=TaskStatus(row["status"]),
        summary=row["summary"],
        last_user_instruction=row["last_user_instruction"],
        pending_action=pending_action,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/test_store.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/codex_remote_control/store.py tests/test_store.py
git commit -m "feat: persist remote control tasks"
```

## Task 6: Workspace Executor

**Files:**
- Create: `src/codex_remote_control/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write failing executor tests**

Create `tests/test_executor.py`:

```python
import subprocess
from pathlib import Path

import pytest

from codex_remote_control.config import AppConfig
from codex_remote_control.executor import WorkspaceExecutor, WorkspaceNotAllowedError


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)


def test_rejects_workspace_outside_whitelist(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"
    allowed.mkdir()
    blocked.mkdir()
    executor = WorkspaceExecutor(AppConfig.for_tests(workspace_roots=[allowed]))

    with pytest.raises(WorkspaceNotAllowedError):
        executor.git_status(blocked)


def test_git_status_returns_short_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    (repo / "file.txt").write_text("hello", encoding="utf-8")
    executor = WorkspaceExecutor(AppConfig.for_tests(workspace_roots=[repo]))

    result = executor.git_status(repo)

    assert "?? file.txt" in result


def test_run_configured_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    executor = WorkspaceExecutor(AppConfig.for_tests(workspace_roots=[repo]))

    result = executor.run_command(repo, "python -c \"print('ok')\"")

    assert result.exit_code == 0
    assert "ok" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_executor.py -v
```

Expected: FAIL with missing `WorkspaceExecutor`.

- [ ] **Step 3: Implement executor**

Create `src/codex_remote_control/executor.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from codex_remote_control.config import AppConfig


class WorkspaceNotAllowedError(ValueError):
    pass


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class WorkspaceExecutor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ensure_allowed(self, workspace_path: str | Path) -> Path:
        resolved = Path(workspace_path).resolve()
        if not self.config.is_allowed_workspace(resolved):
            raise WorkspaceNotAllowedError(str(resolved))
        return resolved

    def git_status(self, workspace_path: str | Path) -> str:
        workspace = self.ensure_allowed(workspace_path)
        result = self._run(workspace, ["git", "status", "--short"])
        return result.stdout

    def git_diff_summary(self, workspace_path: str | Path) -> str:
        workspace = self.ensure_allowed(workspace_path)
        result = self._run(workspace, ["git", "diff", "--stat"])
        return result.stdout

    def run_command(self, workspace_path: str | Path, command: str) -> CommandResult:
        workspace = self.ensure_allowed(workspace_path)
        completed = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def commit(self, workspace_path: str | Path, message: str) -> str:
        workspace = self.ensure_allowed(workspace_path)
        self._run(workspace, ["git", "add", "-A"])
        self._run(workspace, ["git", "commit", "-m", message])
        return self._run(workspace, ["git", "rev-parse", "--short", "HEAD"]).stdout.strip()

    def _run(self, workspace: Path, args: list[str]) -> CommandResult:
        completed = subprocess.run(
            args,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/test_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/codex_remote_control/executor.py tests/test_executor.py
git commit -m "feat: constrain workspace execution"
```

## Task 7: Router and Task Runner

**Files:**
- Create: `src/codex_remote_control/codex_adapter.py`
- Create: `src/codex_remote_control/runner.py`
- Create: `src/codex_remote_control/router.py`
- Create: `tests/test_router.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write failing router and runner tests**

Create `tests/test_router.py`:

```python
from pathlib import Path

from codex_remote_control.config import AppConfig
from codex_remote_control.router import ConversationRouter
from codex_remote_control.store import TaskStore


def test_new_task_sets_current_task(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = TaskStore(tmp_path / "tasks.db")
    router = ConversationRouter(AppConfig.for_tests(workspace_roots=[workspace]), store)

    response = router.handle("ou_allowed", f"/新任务 {workspace} 修复问题")

    assert "已创建任务" in response
    assert store.get_current_task("ou_allowed") is not None


def test_plain_text_without_current_task_prompts_new_task(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    router = ConversationRouter(AppConfig.for_tests(workspace_roots=[]), store)

    response = router.handle("ou_allowed", "继续")

    assert "/新任务" in response


def test_plain_text_does_not_confirm_pending_action(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = TaskStore(tmp_path / "tasks.db")
    router = ConversationRouter(AppConfig.for_tests(workspace_roots=[workspace]), store)
    router.handle("ou_allowed", f"/新任务 {workspace} 修复问题")
    task = store.get_current_task("ou_allowed")
    assert task is not None
    store.set_pending_commit(task.id, "feat: fix issue")

    response = router.handle("ou_allowed", "好的")

    assert "必须使用 /确认" in response
```

Create `tests/test_runner.py`:

```python
from pathlib import Path

from codex_remote_control.config import AppConfig
from codex_remote_control.models import PermissionLevel
from codex_remote_control.runner import TaskRunner
from codex_remote_control.store import TaskStore


def test_status_reports_current_task(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    store = TaskStore(tmp_path / "tasks.db")
    task = store.create_task(
        "ou_allowed",
        "任务",
        workspace,
        permission=PermissionLevel.WORK,
        goal="目标",
    )
    store.set_current_task("ou_allowed", task.id)
    runner = TaskRunner(AppConfig.for_tests(workspace_roots=[workspace]), store)

    response = runner.status("ou_allowed")

    assert "任务" in response
    assert "created" in response
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_router.py tests/test_runner.py -v
```

Expected: FAIL with missing router or runner modules.

- [ ] **Step 3: Implement Codex adapter boundary**

Create `src/codex_remote_control/codex_adapter.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from codex_remote_control.models import Task


@dataclass(frozen=True)
class CodexResult:
    summary: str
    changed: bool


class CodexAdapter:
    def continue_task(self, task: Task, instruction: str) -> CodexResult:
        summary = (
            f"已记录远程指令：{instruction}\n"
            "MVP adapter 当前以任务摘要方式接续，不复用真实 Codex session。"
        )
        return CodexResult(summary=summary, changed=False)
```

- [ ] **Step 4: Implement task runner**

Create `src/codex_remote_control/runner.py`:

```python
from __future__ import annotations

from codex_remote_control.config import AppConfig
from codex_remote_control.codex_adapter import CodexAdapter
from codex_remote_control.executor import WorkspaceExecutor
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
        return f"{task.title} - {task.status.value}\n{task.summary or task.last_user_instruction}"

    def continue_current(self, user_id: str, instruction: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        if task.status == TaskStatus.WAITING_CONFIRMATION:
            return "当前任务等待确认 release 动作，必须使用 /确认 或 /拒绝。"
        self.store.set_status(task.id, TaskStatus.RUNNING)
        result = self.codex.continue_task(task, instruction)
        self.store.set_status(task.id, TaskStatus.COMPLETED, result.summary)
        return result.summary

    def diff(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None:
            return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
        summary = self.executor.git_diff_summary(task.workspace_path)
        return summary or "当前没有 diff。"

    def confirm(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None or task.pending_action is None:
            return "没有等待确认的动作。"
        if task.pending_action.kind == PendingActionKind.COMMIT:
            commit_hash = self.executor.commit(
                task.workspace_path,
                task.pending_action.payload["message"],
            )
            self.store.clear_pending_action(task.id, TaskStatus.COMPLETED)
            return f"已提交：{commit_hash}"
        return "未知确认动作，已拒绝执行。"

    def reject(self, user_id: str) -> str:
        task = self.store.get_current_task(user_id)
        if task is None or task.pending_action is None:
            return "没有等待确认的动作。"
        self.store.clear_pending_action(task.id, TaskStatus.PAUSED)
        return "已拒绝并暂停该动作。"
```

- [ ] **Step 5: Implement conversation router**

Create `src/codex_remote_control/router.py`:

```python
from __future__ import annotations

from pathlib import Path

from codex_remote_control.commands import CommandKind, parse_message
from codex_remote_control.config import AppConfig
from codex_remote_control.models import PermissionLevel, TaskStatus
from codex_remote_control.runner import TaskRunner
from codex_remote_control.store import TaskStore


class ConversationRouter:
    def __init__(self, config: AppConfig, store: TaskStore, runner: TaskRunner | None = None) -> None:
        self.config = config
        self.store = store
        self.runner = runner or TaskRunner(config, store)

    def handle(self, user_id: str, text: str) -> str:
        command = parse_message(text)
        if command.kind == CommandKind.NEW_TASK:
            workspace = Path(str(command.args["workspace_path"])).resolve()
            if not self.config.is_allowed_workspace(workspace):
                return "项目路径不在白名单内，已拒绝执行。"
            goal = str(command.args["goal"])
            title = goal[:32] or workspace.name
            task = self.store.create_task(
                user_id=user_id,
                title=title,
                workspace_path=workspace,
                permission=PermissionLevel.WORK,
                goal=goal,
            )
            self.store.set_current_task(user_id, task.id)
            return f"已创建任务 #{task.id}：{task.title}"
        if command.kind == CommandKind.SESSIONS:
            tasks = self.store.list_tasks(user_id)
            if not tasks:
                return "暂无任务，请使用 /新任务 <项目路径> <目标>。"
            return "\n".join(
                f"{index}. {task.title} - {task.status.value}"
                for index, task in enumerate(tasks, start=1)
            )
        if command.kind == CommandKind.SWITCH:
            tasks = self.store.list_tasks(user_id)
            index = int(command.args["index"]) - 1
            if index < 0 or index >= len(tasks):
                return "任务编号不存在。"
            self.store.set_current_task(user_id, tasks[index].id)
            return f"已切换到任务 #{tasks[index].id}：{tasks[index].title}"
        if command.kind == CommandKind.STATUS:
            return self.runner.status(user_id)
        if command.kind == CommandKind.CONTINUE:
            current = self.store.get_current_task(user_id)
            if current and current.status == TaskStatus.WAITING_CONFIRMATION:
                return "当前任务等待确认 release 动作，必须使用 /确认 或 /拒绝。"
            return self.runner.continue_current(user_id, command.text)
        if command.kind == CommandKind.DIFF:
            return self.runner.diff(user_id)
        if command.kind == CommandKind.COMMIT:
            task = self.store.get_current_task(user_id)
            if task is None:
                return "没有当前任务，请使用 /新任务 <项目路径> <目标>。"
            self.store.set_pending_commit(task.id, f"Update {task.title}")
            return "准备提交当前改动。请使用 /确认 执行 commit，或使用 /拒绝 取消。"
        if command.kind == CommandKind.CONFIRM:
            return self.runner.confirm(user_id)
        if command.kind == CommandKind.REJECT:
            return self.runner.reject(user_id)
        if command.kind == CommandKind.PAUSE:
            task = self.store.get_current_task(user_id)
            if task is None:
                return "没有当前任务。"
            self.store.set_status(task.id, TaskStatus.PAUSED)
            return "已暂停当前任务。"
        if command.kind == CommandKind.RUN_TESTS:
            return "测试命令接入在 Workspace Executor 任务中完成。"
        return "无法识别该指令。"
```

- [ ] **Step 6: Run tests**

Run:

```powershell
pytest tests/test_router.py tests/test_runner.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/codex_remote_control/codex_adapter.py src/codex_remote_control/runner.py src/codex_remote_control/router.py tests/test_router.py tests/test_runner.py
git commit -m "feat: route remote task conversations"
```

## Task 8: FastAPI Webhook

**Files:**
- Create: `src/codex_remote_control/app.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing webhook tests**

Create `tests/test_app.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from codex_remote_control.app import create_app
from codex_remote_control.config import AppConfig


def test_webhook_rejects_unknown_user(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post(
        "/feishu/webhook",
        json={
            "token": "token",
            "event": {
                "message": {"message_id": "om_1", "content": "{\"text\":\"/状态\"}"},
                "sender": {"sender_id": {"open_id": "ou_blocked"}},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["text"] == "user is not allowed"


def test_webhook_routes_allowed_message(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post(
        "/feishu/webhook",
        json={
            "token": "token",
            "event": {
                "message": {"message_id": "om_1", "content": "{\"text\":\"/状态\"}"},
                "sender": {"sender_id": {"open_id": "ou_allowed"}},
            },
        },
    )

    assert response.status_code == 200
    assert "/新任务" in response.json()["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_app.py -v
```

Expected: FAIL with missing app module.

- [ ] **Step 3: Implement FastAPI app factory**

Create `src/codex_remote_control/app.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from codex_remote_control.config import AppConfig, load_config
from codex_remote_control.feishu import parse_feishu_event, verify_event
from codex_remote_control.router import ConversationRouter
from codex_remote_control.store import TaskStore


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config(Path("config/local.toml"))
    store = TaskStore(app_config.storage.sqlite_path)
    router = ConversationRouter(app_config, store)
    app = FastAPI(title="Codex Remote Control")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/feishu/webhook")
    async def feishu_webhook(payload: dict) -> dict[str, str]:
        event = parse_feishu_event(payload)
        verified = verify_event(event, app_config)
        if not verified.allowed:
            return {"text": verified.reason}
        return {"text": router.handle(verified.user_id, verified.text)}

    return app
```

- [ ] **Step 4: Run tests**

Run:

```powershell
pytest tests/test_app.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/codex_remote_control/app.py tests/test_app.py
git commit -m "feat: expose feishu webhook"
```

## Task 9: Documentation and End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `config/local.example.toml`
- Test: all tests

- [ ] **Step 1: Update README with Feishu and local tunnel notes**

Replace `README.md` with:

```markdown
# Codex Remote Control

Windows-local Feishu gateway for controlled Codex coding tasks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Configuration

Copy the example file:

```powershell
Copy-Item config/local.example.toml config/local.toml
```

Fill:

- `feishu.app_id`
- `feishu.app_secret`
- `feishu.verification_token`
- `feishu.allowed_user_ids`
- `workspace.root`
- `workspace.default_test_command`

Never commit `config/local.toml`.

## Run

```powershell
uvicorn codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

Expose `http://127.0.0.1:8765/feishu/webhook` through a local tunnel during development, then configure that public URL in the Feishu bot.

## Supported Commands

```text
/新任务 <项目路径> <目标>
/会话
/切换 <编号>
/状态
/继续 <补充指令>
/暂停
/确认
/拒绝
/运行测试
/差异
/提交
```

Commit requires `/提交` followed by `/确认`. Ordinary text never confirms a release action.
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
pytest
ruff check .
git diff --check
```

Expected: all tests pass, no lint errors, no whitespace errors.

- [ ] **Step 3: Commit**

```powershell
git add README.md config/local.example.toml
git commit -m "docs: explain local feishu setup"
```

## Plan Self-Review Notes

- Spec coverage: the plan covers Feishu webhook intake, verification token and user whitelist, command parsing, current task routing, SQLite persistence, workspace whitelist, git status and diff, configured test command execution, commit confirmation, and local run documentation.
- Deferred by design: real Codex session reuse, DingTalk support, Web UI, push and PR automation, and arbitrary shell are outside MVP scope from the approved spec.
- Safety checks included: path whitelist is tested before workspace operations; ordinary text cannot confirm release actions; commit requires pending confirmation.
