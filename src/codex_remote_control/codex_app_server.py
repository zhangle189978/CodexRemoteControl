from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import websockets


class CodexAppServerUnavailable(RuntimeError):
    pass


class CodexAppServerTurnFailed(RuntimeError):
    pass


class CodexAppServerClient:
    def __init__(
        self,
        command: str = "codex",
        startup_timeout: float = 20.0,
        turn_timeout: float = 60 * 60,
    ) -> None:
        self.command = command
        self.startup_timeout = startup_timeout
        self.turn_timeout = turn_timeout

    def run_turn(self, thread_id: str, instruction: str, cwd: Path) -> str:
        result: dict[str, str] = {}
        error: dict[str, BaseException] = {}

        def target() -> None:
            try:
                result["value"] = asyncio.run(self._run_turn_async(thread_id, instruction, cwd))
            except BaseException as exc:
                error["value"] = exc

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(self.turn_timeout + self.startup_timeout)
        if thread.is_alive():
            raise TimeoutError("Codex app-server turn timed out")
        if "value" in error:
            raise error["value"]
        return result.get("value", "")

    async def _run_turn_async(self, thread_id: str, instruction: str, cwd: Path) -> str:
        port = _free_local_port()
        uri = f"ws://127.0.0.1:{port}"
        turn_started = False
        process = subprocess.Popen(
            _command_for_subprocess([self.command, "app-server", "--listen", uri]),
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        try:
            _wait_for_healthz(port, self.startup_timeout)
            async with websockets.connect(uri, max_size=30_000_000) as ws:
                rpc = _JsonRpc(ws)
                await rpc.request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "codex-remote-control",
                            "title": "Codex Remote Control",
                            "version": "0.1.0",
                        },
                        "capabilities": {"experimentalApi": True},
                    },
                )
                await rpc.request(
                    "thread/resume",
                    {"threadId": thread_id, "persistExtendedHistory": True},
                    timeout=120,
                )
                started = await rpc.request(
                    "turn/start",
                    {
                        "threadId": thread_id,
                        "input": [
                            {
                                "type": "text",
                                "text": instruction,
                                "text_elements": [],
                            }
                        ],
                    },
                    timeout=120,
                )
                turn_id = _turn_id(started)
                turn_started = True
                return await _collect_turn_text(rpc, turn_id, timeout=self.turn_timeout)
        except Exception as exc:
            if turn_started:
                raise CodexAppServerTurnFailed(str(exc)) from exc
            raise CodexAppServerUnavailable(str(exc)) from exc
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


class _JsonRpc:
    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.next_id = 1
        self.pending_events: list[dict[str, Any]] = []

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        await self.ws.send(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
                ensure_ascii=True,
            )
        )
        while True:
            message = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            event = json.loads(message)
            if event.get("id") == request_id:
                if "error" in event:
                    raise RuntimeError(str(event["error"]))
                return dict(event.get("result") or {})
            if isinstance(event, dict):
                self.pending_events.append(event)

    async def next_event(self, timeout: float = 30) -> dict[str, Any]:
        if self.pending_events:
            return self.pending_events.pop(0)
        message = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        event = json.loads(message)
        return dict(event) if isinstance(event, dict) else {}


async def _collect_turn_text(rpc: _JsonRpc, turn_id: str, timeout: float = 60 * 60) -> str:
    message_text_by_id: dict[str, str] = {}
    deltas_by_id: dict[str, list[str]] = {}
    deadline = time.monotonic() + timeout
    while True:
        remaining = max(1.0, deadline - time.monotonic())
        if remaining <= 1.0 and time.monotonic() >= deadline:
            raise TimeoutError("Codex app-server turn timed out")
        event = await rpc.next_event(timeout=min(300, remaining))
        method = event.get("method")
        params = event.get("params")
        if not isinstance(params, dict) or params.get("turnId") != turn_id:
            continue
        if method == "error":
            return _format_turn_error(params)
        if method == "item/agentMessage/delta":
            item_id = str(params.get("itemId") or "")
            delta = params.get("delta")
            if item_id and isinstance(delta, str):
                deltas_by_id.setdefault(item_id, []).append(delta)
        if method == "item/completed":
            item = params.get("item")
            if isinstance(item, dict) and item.get("type") == "agentMessage":
                item_id = str(item.get("id") or "")
                text = item.get("text")
                if item_id and isinstance(text, str):
                    message_text_by_id[item_id] = text
        if method == "turn/completed":
            turn = params.get("turn")
            if isinstance(turn, dict) and turn.get("status") == "failed":
                return _format_turn_error(turn)
            if message_text_by_id:
                return "\n".join(text for text in message_text_by_id.values() if text).strip()
            return "\n".join("".join(parts) for parts in deltas_by_id.values()).strip()


def _turn_id(started: dict[str, Any]) -> str:
    turn = started.get("turn")
    if not isinstance(turn, dict) or not isinstance(turn.get("id"), str):
        raise RuntimeError("turn/start did not return a turn id")
    return turn["id"]


def _format_turn_error(params: dict[str, Any]) -> str:
    error = params.get("error")
    if not isinstance(error, dict):
        return "Codex turn failed."
    message = error.get("message")
    detail = error.get("additionalDetails")
    parts = [part for part in (message, detail) if isinstance(part, str) and part.strip()]
    if not parts:
        return "Codex turn failed."
    return "Codex turn failed: " + "\n".join(parts)


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_healthz(port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/healthz"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if 200 <= response.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    raise TimeoutError("Codex app-server did not become healthy")


def _command_for_subprocess(command: list[str]) -> list[str]:
    if not command:
        return command
    executable = shutil.which(command[0]) or command[0]
    suffix = Path(executable).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        return ["cmd.exe", "/c", executable, *command[1:]]
    return [executable, *command[1:]]
