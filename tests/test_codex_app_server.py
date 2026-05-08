import asyncio

from codex_remote_control.codex_app_server import _collect_turn_text


class FakeRpc:
    def __init__(self, events):
        self.events = list(events)

    async def next_event(self, timeout: float = 30):
        return self.events.pop(0)


def test_collect_turn_text_prefers_completed_agent_message() -> None:
    rpc = FakeRpc(
        [
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "turnId": "turn-1",
                    "itemId": "msg-1",
                    "delta": "PO",
                },
            },
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "turnId": "turn-1",
                    "itemId": "msg-1",
                    "delta": "C",
                },
            },
            {
                "method": "item/completed",
                "params": {
                    "turnId": "turn-1",
                    "item": {
                        "type": "agentMessage",
                        "id": "msg-1",
                        "text": "POC_OK",
                    },
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "turnId": "turn-1",
                    "turn": {"status": "completed"},
                },
            },
        ]
    )

    text = asyncio.run(_collect_turn_text(rpc, "turn-1"))

    assert text == "POC_OK"


def test_collect_turn_text_falls_back_to_deltas() -> None:
    rpc = FakeRpc(
        [
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "turnId": "turn-1",
                    "itemId": "msg-1",
                    "delta": "PO",
                },
            },
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "turnId": "turn-1",
                    "itemId": "msg-1",
                    "delta": "C_OK",
                },
            },
            {
                "method": "turn/completed",
                "params": {
                    "turnId": "turn-1",
                    "turn": {"status": "completed"},
                },
            },
        ]
    )

    text = asyncio.run(_collect_turn_text(rpc, "turn-1"))

    assert text == "POC_OK"


def test_collect_turn_text_returns_codex_error_message() -> None:
    rpc = FakeRpc(
        [
            {
                "method": "error",
                "params": {
                    "turnId": "turn-1",
                    "error": {
                        "message": "Codex ran out of room in the model's context window.",
                        "additionalDetails": "Start a new thread before retrying.",
                    },
                },
            },
        ]
    )

    text = asyncio.run(_collect_turn_text(rpc, "turn-1"))

    assert "Codex ran out of room" in text
    assert "Start a new thread" in text


def test_collect_turn_text_returns_failed_turn_error_message() -> None:
    rpc = FakeRpc(
        [
            {
                "method": "turn/completed",
                "params": {
                    "turnId": "turn-1",
                    "turn": {
                        "status": "failed",
                        "error": {
                            "message": "context window exceeded",
                            "additionalDetails": None,
                        },
                    },
                },
            },
        ]
    )

    text = asyncio.run(_collect_turn_text(rpc, "turn-1"))

    assert text == "Codex turn failed: context window exceeded"
