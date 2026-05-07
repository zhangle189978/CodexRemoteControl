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
    event = payload["event"]
    message = event["message"]
    content = json.loads(message["content"])

    return FeishuEvent(
        token=payload["token"],
        user_id=event["sender"]["sender_id"]["open_id"],
        text=content["text"],
        message_id=message["message_id"],
    )


def verify_event(event: FeishuEvent, config: AppConfig) -> VerifiedEvent:
    if event.token != config.feishu.verification_token:
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
