from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CodexSession:
    session_id: str
    thread_name: str
    updated_at: datetime
    workspace_path: Path | None
    summary: str

    @property
    def short_id(self) -> str:
        return self.session_id[-8:]


class CodexSessionSource:
    def __init__(self, codex_home: str | Path | None = None) -> None:
        self.codex_home = Path(codex_home or Path.home() / ".codex")

    def list_recent(self, limit: int = 5) -> list[CodexSession]:
        index_path = self.codex_home / "session_index.jsonl"
        indexed: dict[str, dict[str, Any]] = {}
        if index_path.exists():
            indexed = {
                str(row["id"]): row for row in _read_jsonl(index_path) if _is_index_row(row)
            }
        rollout_by_id = {session.session_id: session for session in self._list_rollout_sessions()}
        sessions = [
            self._merge_index_and_rollout(row, rollout_by_id.get(str(row["id"])))
            for row in indexed.values()
        ]
        indexed_ids = {session.session_id for session in sessions}
        sessions.extend(
            session
            for session in rollout_by_id.values()
            if session.session_id not in indexed_ids
        )
        sessions.sort(key=lambda session: session.updated_at, reverse=True)
        return sessions[:limit]

    def get_by_index(self, index: int) -> CodexSession | None:
        if index < 1:
            return None
        sessions = self.list_recent(limit=index)
        if index > len(sessions):
            return None
        return sessions[index - 1]

    def _build_session(self, row: dict[str, Any]) -> CodexSession:
        session_id = str(row["id"])
        workspace_path, summary = self._read_rollout_details(session_id)
        return CodexSession(
            session_id=session_id,
            thread_name=str(row.get("thread_name") or session_id),
            updated_at=_parse_datetime(str(row["updated_at"])),
            workspace_path=workspace_path,
            summary=summary,
        )

    def _merge_index_and_rollout(
        self,
        row: dict[str, Any],
        rollout_session: CodexSession | None,
    ) -> CodexSession:
        indexed_session = self._build_session(row)
        if rollout_session is None:
            return indexed_session
        if rollout_session.updated_at > indexed_session.updated_at:
            return rollout_session
        return indexed_session

    def _read_rollout_details(self, session_id: str) -> tuple[Path | None, str]:
        rollout_path = self._find_rollout_path(session_id)
        if rollout_path is None:
            return None, ""
        workspace_path: Path | None = None
        message_snippets: list[str] = []
        for row in _read_jsonl(rollout_path):
            if row.get("type") == "session_meta":
                payload = row.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
                    workspace_path = Path(payload["cwd"])
            if row.get("type") == "response_item":
                payload = row.get("payload")
                message_text = _extract_message_text(payload)
                if message_text:
                    message_snippets.append(message_text)
        return workspace_path, _truncate("\n".join(message_snippets[-6:]), 600)

    def _list_rollout_sessions(self) -> list[CodexSession]:
        sessions_dir = self.codex_home / "sessions"
        if not sessions_dir.exists():
            return []
        sessions: list[CodexSession] = []
        for rollout_path in sessions_dir.rglob("*.jsonl"):
            session = self._session_from_rollout(rollout_path)
            if session is not None:
                sessions.append(session)
        return sessions

    def _session_from_rollout(self, rollout_path: Path) -> CodexSession | None:
        session_id = ""
        workspace_path: Path | None = None
        thread_name = ""
        message_snippets: list[str] = []
        updated_at: datetime | None = None
        for row in _read_jsonl(rollout_path):
            timestamp = row.get("timestamp")
            if isinstance(timestamp, str):
                updated_at = _parse_datetime(timestamp)
            if row.get("type") == "session_meta":
                payload = row.get("payload")
                if isinstance(payload, dict):
                    if isinstance(payload.get("id"), str):
                        session_id = payload["id"]
                    if isinstance(payload.get("cwd"), str):
                        workspace_path = Path(payload["cwd"])
            if row.get("type") == "event_msg":
                payload = row.get("payload")
                if isinstance(payload, dict) and payload.get("type") == "thread_name_updated":
                    if isinstance(payload.get("thread_name"), str):
                        thread_name = payload["thread_name"]
            if row.get("type") == "response_item":
                payload = row.get("payload")
                message_text = _extract_message_text(payload)
                if message_text:
                    message_snippets.append(message_text)
        if not session_id or updated_at is None:
            return None
        return CodexSession(
            session_id=session_id,
            thread_name=thread_name or session_id,
            updated_at=updated_at,
            workspace_path=workspace_path,
            summary=_truncate("\n".join(message_snippets[-6:]), 600),
        )

    def _find_rollout_path(self, session_id: str) -> Path | None:
        sessions_dir = self.codex_home / "sessions"
        if not sessions_dir.exists():
            return None
        matches = sorted(sessions_dir.rglob(f"*{session_id}.jsonl"))
        return matches[-1] if matches else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _is_index_row(row: dict[str, Any]) -> bool:
    return isinstance(row.get("id"), str) and isinstance(row.get("updated_at"), str)


def _parse_datetime(raw: str) -> datetime:
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _extract_message_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    if payload.get("type") != "message":
        return ""
    role = payload.get("role")
    if role == "user":
        label = "用户"
    elif role == "assistant":
        label = "助手"
    else:
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    texts: list[str] = []
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"].strip())
    text = "\n".join(text for text in texts if text).strip()
    if not text:
        return ""
    return f"{label}：{text}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
