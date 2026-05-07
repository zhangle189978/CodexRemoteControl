from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass

from codex_remote_control.config import AppConfig


class DingtalkParseError(ValueError):
    pass


@dataclass(frozen=True)
class DingtalkEvent:
    token: str
    user_id: str
    text: str
    message_id: str
    conversation_id: str


@dataclass(frozen=True)
class VerifiedDingtalkEvent:
    allowed: bool
    user_id: str
    text: str
    message_id: str
    conversation_id: str
    reason: str = ""


def parse_dingtalk_event(payload: Mapping[str, object]) -> DingtalkEvent:
    token = _string_value(payload, "token", "gatewayToken")
    text = _extract_text(payload)
    user_id = _string_value(payload, "senderStaffId", "senderId", "senderNick", "userId")
    message_id = _string_value(payload, "msgId", "messageId")
    conversation_id = _string_value(payload, "conversationId", "conversationTitle")
    if not token:
        raise DingtalkParseError("missing token")
    if not text:
        raise DingtalkParseError("missing text")
    if not user_id:
        raise DingtalkParseError("missing sender")
    if not message_id:
        raise DingtalkParseError("missing message id")
    if not conversation_id:
        raise DingtalkParseError("missing conversation id")
    return DingtalkEvent(
        token=token,
        user_id=user_id,
        text=text,
        message_id=message_id,
        conversation_id=conversation_id,
    )


def verify_dingtalk_event(event: DingtalkEvent, config: AppConfig) -> VerifiedDingtalkEvent:
    if not config.dingtalk.enabled:
        return _denied(event, "dingtalk channel is disabled")
    if not hmac.compare_digest(event.token, config.dingtalk.gateway_token):
        return _denied(event, "invalid gateway token")
    if config.dingtalk.allowed_user_ids and event.user_id not in config.dingtalk.allowed_user_ids:
        return _denied(event, "user is not allowed")
    return VerifiedDingtalkEvent(
        allowed=True,
        user_id=event.user_id,
        text=event.text,
        message_id=event.message_id,
        conversation_id=event.conversation_id,
    )


def format_dingtalk_text_response(text: str) -> dict[str, object]:
    return {"msgtype": "text", "text": {"content": text}}


def _extract_text(payload: Mapping[str, object]) -> str:
    text = payload.get("text")
    if isinstance(text, str):
        return text.strip()
    if isinstance(text, Mapping):
        content = text.get("content")
        if isinstance(content, str):
            return content.strip()
    content = payload.get("content")
    if isinstance(content, Mapping):
        inner_text = content.get("text")
        if isinstance(inner_text, str):
            return inner_text.strip()
    return ""


def _string_value(payload: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _denied(event: DingtalkEvent, reason: str) -> VerifiedDingtalkEvent:
    return VerifiedDingtalkEvent(
        allowed=False,
        user_id=event.user_id,
        text=event.text,
        message_id=event.message_id,
        conversation_id=event.conversation_id,
        reason=reason,
    )
