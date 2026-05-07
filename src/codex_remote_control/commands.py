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
    INVALID = "invalid"


@dataclass(frozen=True)
class ParsedCommand:
    kind: CommandKind
    text: str = ""
    args: dict[str, object] = field(default_factory=dict)


def parse_message(text: str) -> ParsedCommand:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ParsedCommand(kind=CommandKind.CONTINUE, text=stripped)

    parts = stripped.split(maxsplit=1)
    name = parts[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    match name:
        case "/新任务":
            workspace_path, has_goal, goal = rest.partition(" ")
            if not workspace_path or not has_goal or not goal.strip():
                return ParsedCommand(
                    kind=CommandKind.INVALID,
                    text="用法：/新任务 <项目路径> <目标>",
                )
            return ParsedCommand(
                kind=CommandKind.NEW_TASK,
                args={"workspace_path": workspace_path, "goal": goal.strip()},
            )
        case "/会话":
            return ParsedCommand(kind=CommandKind.SESSIONS)
        case "/切换":
            if not rest.isdecimal():
                return ParsedCommand(kind=CommandKind.INVALID, text="用法：/切换 <编号>")
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
