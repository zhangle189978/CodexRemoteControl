from __future__ import annotations

import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from json import JSONDecodeError

from codex_remote_control.config import AppConfig


class FeishuParseError(ValueError):
    pass


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
    try:
        event = payload["event"]
        message = event["message"]
        content_raw = message["content"]
        user_id = event["sender"]["sender_id"]["open_id"]
        message_id = message["message_id"]
        token = payload.get("token", "")
    except KeyError as error:
        raise FeishuParseError(f"missing required field: {error.args[0]}") from error

    try:
        content = json.loads(content_raw)
    except (JSONDecodeError, TypeError) as error:
        raise FeishuParseError("invalid message content") from error
    if not isinstance(content, Mapping) or not isinstance(content.get("text"), str):
        raise FeishuParseError("missing text")

    return FeishuEvent(
        token=token,
        user_id=user_id,
        text=content["text"],
        message_id=message_id,
    )


def verify_event(event: FeishuEvent, config: AppConfig) -> VerifiedEvent:
    if not hmac.compare_digest(event.token, config.feishu.verification_token):
        return _denied(event, "invalid verification token")
    if event.user_id not in config.feishu.allowed_user_ids:
        return _denied(event, "user is not allowed")
    return VerifiedEvent(
        allowed=True,
        user_id=event.user_id,
        text=event.text,
        message_id=event.message_id,
    )


def _denied(event: FeishuEvent, reason: str) -> VerifiedEvent:
    return VerifiedEvent(
        allowed=False,
        user_id=event.user_id,
        text=event.text,
        message_id=event.message_id,
        reason=reason,
    )
