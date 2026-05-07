import json
from pathlib import Path

from codex_remote_control.config import AppConfig
from codex_remote_control.feishu import FeishuEvent, parse_feishu_event, verify_event


def test_allowed_token_and_user_returns_allowed_result() -> None:
    event = FeishuEvent(
        token="token",
        user_id="ou_allowed",
        text="/状态",
        message_id="om_1",
    )

    verified = verify_event(event, AppConfig.for_tests())

    assert verified.allowed is True
    assert verified.user_id == "ou_allowed"
    assert verified.text == "/状态"
    assert verified.message_id == "om_1"
    assert verified.reason == ""


def test_bad_token_returns_invalid_verification_token() -> None:
    event = FeishuEvent(
        token="bad",
        user_id="ou_allowed",
        text="/状态",
        message_id="om_1",
    )

    verified = verify_event(event, AppConfig.for_tests())

    assert verified.allowed is False
    assert verified.reason == "invalid verification token"


def test_unknown_user_returns_user_is_not_allowed() -> None:
    event = FeishuEvent(
        token="token",
        user_id="ou_unknown",
        text="/状态",
        message_id="om_1",
    )

    verified = verify_event(event, AppConfig.for_tests())

    assert verified.allowed is False
    assert verified.reason == "user is not allowed"


def test_fixture_json_can_be_parsed() -> None:
    fixture = Path(__file__).parent / "fixtures" / "feishu_message.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))

    event = parse_feishu_event(payload)

    assert event.message_id == "om_1"
    assert event.user_id == "ou_allowed"
    assert event.text == "/状态"
