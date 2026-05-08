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
-> inject text into the active Codex Desktop GUI
-> wait for the next assistant reply or Codex error in the rollout file
-> reply to chat
```

If GUI injection cannot be used, the adapter falls back to the experimental
app-server path:

```text
codex app-server --listen ws://127.0.0.1:<free-port>
-> initialize
-> thread/resume
-> turn/start
-> collect assistant deltas, completed messages, or error notifications
```

If app-server cannot be used, the adapter falls back again to:

```text
codex exec resume <session-id> <instruction>
```

## Desktop UI Behavior

GUI injection targets the currently visible Codex Desktop window. The Codex
window must be open, foregroundable, idle, and already on the session that the
remote user wants to control.

Consequence:

- The mobile turn runs in the visible desktop session when injection succeeds.
- `/进展`, `/尾巴`, and `/刷新` can read the resulting rollout records from
  DingTalk.
- If injection fails, app-server and CLI resume fallbacks may persist to the same
  session record without live-updating the already-open desktop UI.

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
