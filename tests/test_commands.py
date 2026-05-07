from codex_remote_control.commands import CommandKind, parse_message


def test_parses_new_task_with_workspace_and_instruction() -> None:
    command = parse_message(r"/新任务 C:\Users\89493\Documents\HollyDB 修复索引问题")

    assert command.kind is CommandKind.NEW_TASK
    assert command.text == ""
    assert command.args == {
        "workspace_path": r"C:\Users\89493\Documents\HollyDB",
        "goal": "修复索引问题",
    }


def test_parses_continue_command_with_instruction() -> None:
    command = parse_message("/继续 按方案二实现")

    assert command.kind is CommandKind.CONTINUE
    assert command.text == "按方案二实现"
    assert command.args == {}


def test_treats_ordinary_text_as_continue() -> None:
    command = parse_message("按方案二实现")

    assert command.kind is CommandKind.CONTINUE
    assert command.text == "按方案二实现"
    assert command.args == {}


def test_parses_switch_session_number() -> None:
    command = parse_message("/切换 2")

    assert command.kind is CommandKind.SWITCH
    assert command.text == ""
    assert command.args == {"index": 2}


def test_parses_confirmation_commands() -> None:
    assert parse_message("/提交").kind is CommandKind.COMMIT
    assert parse_message("/确认").kind is CommandKind.CONFIRM
    assert parse_message("/拒绝").kind is CommandKind.REJECT


def test_parses_simple_control_commands() -> None:
    assert parse_message("/会话").kind is CommandKind.SESSIONS
    assert parse_message("/状态").kind is CommandKind.STATUS
    assert parse_message("/暂停").kind is CommandKind.PAUSE
    assert parse_message("/运行测试").kind is CommandKind.RUN_TESTS
    assert parse_message("/差异").kind is CommandKind.DIFF


def test_treats_unknown_slash_command_as_continue() -> None:
    command = parse_message("/未知 做这件事")

    assert command.kind is CommandKind.CONTINUE
    assert command.text == "/未知 做这件事"
    assert command.args == {}
