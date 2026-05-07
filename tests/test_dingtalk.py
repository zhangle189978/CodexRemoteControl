import pytest

from codex_remote_control.config import AppConfig, DingtalkConfig
from codex_remote_control.dingtalk import (
    DingtalkParseError,
    format_dingtalk_text_response,
    parse_dingtalk_event,
    verify_dingtalk_event,
)


def _payload(token: str = "ding_token") -> dict[str, object]:
    return {
        "token": token,
        "msgId": "ding_msg_1",
        "conversationId": "cid_1",
        "senderStaffId": "user_1",
        "text": {"content": " /状态 "},
    }


def test_parse_dingtalk_event() -> None:
    event = parse_dingtalk_event(_payload())

    assert event.token == "ding_token"
    assert event.user_id == "user_1"
    assert event.text == "/状态"
    assert event.message_id == "ding_msg_1"
    assert event.conversation_id == "cid_1"


def test_parse_dingtalk_event_supports_flat_text() -> None:
    payload = _payload()
    payload["text"] = "继续这个任务"

    event = parse_dingtalk_event(payload)

    assert event.text == "继续这个任务"


def test_parse_dingtalk_event_rejects_missing_text() -> None:
    payload = _payload()
    del payload["text"]

    with pytest.raises(DingtalkParseError, match="missing text"):
        parse_dingtalk_event(payload)


def test_verify_dingtalk_event_rejects_invalid_gateway_token() -> None:
    config = AppConfig.for_tests()
    event = parse_dingtalk_event(_payload(token="wrong"))

    verified = verify_dingtalk_event(event, config)

    assert not verified.allowed
    assert verified.reason == "invalid gateway token"


def test_verify_dingtalk_event_rejects_unknown_user_when_whitelist_is_set() -> None:
    config = AppConfig.for_tests()
    config = AppConfig(
        server=config.server,
        feishu=config.feishu,
        dingtalk=DingtalkConfig(
            enabled=config.dingtalk.enabled,
            client_id=config.dingtalk.client_id,
            client_secret=config.dingtalk.client_secret,
            gateway_token=config.dingtalk.gateway_token,
            gateway_password=config.dingtalk.gateway_password,
            require_mention=config.dingtalk.require_mention,
            group_policy=config.dingtalk.group_policy,
            group_session_scope=config.dingtalk.group_session_scope,
            allowed_user_ids=frozenset({"another_user"}),
        ),
        storage=config.storage,
        codex=config.codex,
        workspaces=config.workspaces,
    )
    event = parse_dingtalk_event(_payload())

    verified = verify_dingtalk_event(event, config)

    assert not verified.allowed
    assert verified.reason == "user is not allowed"


def test_format_dingtalk_text_response() -> None:
    assert format_dingtalk_text_response("ok") == {
        "msgtype": "text",
        "text": {"content": "ok"},
    }
