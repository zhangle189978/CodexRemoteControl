from pathlib import Path

from fastapi.testclient import TestClient

from codex_remote_control.app import create_app
from codex_remote_control.config import AppConfig


def _payload(user_id: str = "ou_allowed", token: str = "token", text: str = "/状态") -> dict:
    return {
        "token": token,
        "event": {
            "message": {
                "message_id": "om_1",
                "content": f'{{"text":"{text}"}}',
            },
            "sender": {"sender_id": {"open_id": user_id}},
        },
    }


def _dingtalk_payload(token: str = "ding_token", text: str = "/状态") -> dict[str, object]:
    return {
        "token": token,
        "msgId": "ding_msg_1",
        "conversationId": "cid_1",
        "senderStaffId": "ding_user_1",
        "text": {"content": text},
    }


def test_health_endpoint(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_rejects_unknown_user(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post("/feishu/webhook", json=_payload(user_id="ou_blocked"))

    assert response.status_code == 200
    assert response.json()["text"] == "user is not allowed"


def test_webhook_routes_allowed_message(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post("/feishu/webhook", json=_payload())

    assert response.status_code == 200
    assert "/新任务" in response.json()["text"]


def test_webhook_returns_controlled_parse_error(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post("/feishu/webhook", json={"token": "token"})

    assert response.status_code == 200
    assert response.json()["text"].startswith("invalid feishu event:")


def test_dingtalk_webhook_rejects_invalid_gateway_token(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post("/dingtalk/webhook", json=_dingtalk_payload(token="wrong"))

    assert response.status_code == 200
    assert response.json()["text"]["content"] == "invalid gateway token"


def test_dingtalk_webhook_routes_allowed_message(tmp_path: Path) -> None:
    config = AppConfig.for_tests(allowed_user_ids=["ou_allowed"], workspace_roots=[tmp_path])
    client = TestClient(create_app(config=config))

    response = client.post("/dingtalk/webhook", json=_dingtalk_payload())

    assert response.status_code == 200
    assert "/新任务" in response.json()["text"]["content"]
