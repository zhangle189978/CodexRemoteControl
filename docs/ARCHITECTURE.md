# Architecture

## Components

- `codex_remote_control.app`: FastAPI entrypoint for Feishu and DingTalk HTTP
  webhooks.
- `codex_remote_control.dingtalk`: DingTalk signing and response handling.
- `scripts/dingtalk_stream_bridge.mjs`: DingTalk Stream bridge. It connects to
  DingTalk, forwards messages to the local HTTP webhook, and replies back to
  the chat.
- `codex_remote_control.commands`: Chinese command parser.
- `codex_remote_control.router`: Chat command router.
- `codex_remote_control.runner`: Task orchestration for status, continue, test,
  diff, and confirmation flows.
- `codex_remote_control.store`: SQLite task state and current-user binding.
- `codex_remote_control.codex_sessions`: Reader for local Codex session index
  and rollout files under `~/.codex`.
- `codex_remote_control.codex_app_server`: Experimental websocket client for
  `codex app-server`.
- `codex_remote_control.codex_adapter`: Boundary between the router/runner and
  Codex execution.

## Data Flow

```text
DingTalk or Feishu
-> FastAPI webhook
-> command parser
-> router
-> task runner
-> Codex adapter or workspace executor
-> local reply
-> DingTalk or Feishu
```

For imported Codex sessions:

```text
/导入最近
-> read ~/.codex/session_index.jsonl and rollout files
-> create local task with source=codex_session

/继续 <instruction>
-> codex app-server --listen ws://127.0.0.1:<free-port>
-> initialize
-> thread/resume
-> turn/start
-> collect assistant deltas, completed messages, or error notifications
-> reply to chat
```

If app-server cannot be used, the adapter falls back to:

```text
codex exec resume <session-id> <instruction>
```

## Desktop UI Behavior

The bridge currently starts its own short-lived app-server process. That process
can resume and write the same thread history, but it is not the same app-server
instance used by the already-open Codex desktop UI.

Consequence:

- The mobile turn is persisted to the same session record.
- `/进展`, `/尾巴`, and `/刷新` can read the new record from DingTalk.
- The open desktop UI may not live-update with that externally written turn.

This is a Codex desktop integration boundary, not a DingTalk routing issue.

## Runtime Files

Local-only runtime files are intentionally ignored:

- `.venv/`
- `node_modules/`
- `.pytest_cache/`
- `.ruff_cache/`
- `config/local.toml`
- `config/data/`
- `logs/`

Only `config/local.example.toml` is safe to commit.

## Push Checklist

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check scripts/dingtalk_stream_bridge.mjs
git diff --check
git status --short
```
