# Codex Session Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let DingTalk import and continue recent Codex desktop sessions, and let the PC side expose the latest Codex session into the remote task list.

**Architecture:** Add a Codex session reader that parses `~/.codex/session_index.jsonl` and matching rollout files into lightweight handoff records. Extend the command parser/router/store with remote user tracking and task creation from imported Codex sessions. Add a PowerShell script for PC-side adoption that uses the most recent remote user when no user id is supplied.

**Tech Stack:** Python 3.12, FastAPI service, sqlite3 store, pytest, PowerShell helper scripts.

---

### Task 1: Codex Session Reader

**Files:**
- Create: `src/codex_remote_control/codex_sessions.py`
- Test: `tests/test_codex_sessions.py`

- [x] Write tests for listing recent sessions from a temporary `.codex` directory.
- [x] Implement `CodexSessionSource.list_recent(limit)` and `CodexSessionSource.get_by_index(index)`.
- [x] Extract workspace hints and summary snippets from rollout JSONL when available.

### Task 2: Store Imported Sessions and Remote Users

**Files:**
- Modify: `src/codex_remote_control/store.py`
- Test: `tests/test_store.py`

- [x] Add `remote_users` table with `last_seen_at`.
- [x] Add `record_remote_user()` and `get_last_remote_user_id()`.
- [x] Add `create_imported_session_task()` storing source metadata in task summary JSON.

### Task 3: DingTalk Commands

**Files:**
- Modify: `src/codex_remote_control/commands.py`
- Modify: `src/codex_remote_control/router.py`
- Test: `tests/test_commands.py`, `tests/test_router.py`

- [x] Add `/最近会话` command.
- [x] Add `/导入最近 [编号]` command.
- [x] Route commands through `CodexSessionSource` and create switchable tasks.

### Task 4: PC-Side Adoption Script

**Files:**
- Create: `src/codex_remote_control/adopt_session.py`
- Create: `scripts/adopt_current_codex_session.ps1`

- [x] Add CLI that imports a recent Codex session for a supplied user id or the last remote user.
- [x] Add PowerShell wrapper reading `config/local.toml`.

### Task 5: Verification and Docs

**Files:**
- Modify: `README.md`

- [x] Document `/最近会话`, `/导入最近 [编号]`, and PC-side adoption.
- [x] Run pytest, ruff, node syntax check, and git diff checks.
- [ ] Commit the feature.
