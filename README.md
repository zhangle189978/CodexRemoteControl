# Codex Remote Control

Windows local gateway for controlling Codex work from DingTalk or Feishu.

The practical target is: start a coding task on the PC, leave the desk, then use
mobile chat to inspect progress, select a Codex session, send follow-up
instructions, and confirm guarded actions.

## Features

- Feishu HTTP webhook.
- DingTalk HTTP webhook.
- DingTalk Stream mode, so local development does not need a public tunnel.
- Task creation, switching, pausing, continuing, diff, tests, and guarded commit.
- Import recent Codex desktop sessions from `~/.codex`.
- Continue imported Codex sessions through the experimental Codex app-server.
- Read imported session progress, tail events, assistant replies, and command
  results from Codex rollout records.
- Require explicit confirmation for release actions such as commit.

## Current Limitation

For imported Codex desktop sessions, `/继续 ...` starts a new turn against the
same Codex thread record. The message is persisted into the same rollout file,
but the currently open Codex desktop UI does not live-refresh external writes.

Observed behavior:

- Mobile command is recorded in the Codex thread history.
- DingTalk can read progress through `/进展`, `/尾巴 20`, or `/刷新`.
- The already-open desktop UI may not display that mobile turn until the app
  reloads or the session is reopened.
- If Codex reports `context window exceeded`, the bridge now returns that error
  instead of silently hanging.

True live injection into the visible desktop UI requires either Codex desktop to
connect to the same long-lived app-server, or a separate UI automation layer that
types into the desktop input box. This repository currently uses the safer
app-server/session-record approach.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install
```

## Configure

```powershell
Copy-Item config/local.example.toml config/local.toml
```

Fill the required local fields:

- `feishu.app_id`
- `feishu.app_secret`
- `feishu.verification_token`
- `feishu.allowed_user_ids`
- `dingtalk.gateway_token`
- `dingtalk.allowed_user_ids`
- `workspace.root`
- `workspace.default_test_command`

Do not commit `config/local.toml`.

## Run

Start the local Python service:

```powershell
.\.venv\Scripts\uvicorn.exe codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

HTTP webhook endpoints:

```text
http://127.0.0.1:8765/feishu/webhook
http://127.0.0.1:8765/dingtalk/webhook
```

For DingTalk Stream mode, keep the Python service running and start:

```powershell
.\scripts\start_dingtalk_stream.ps1
```

The stream bridge reads DingTalk settings from `config/local.toml`, forwards
messages to the local webhook, and sends local replies back to DingTalk.

## Codex Session Handoff

List recent Codex sessions:

```text
/最近会话
```

Import the newest session or a numbered session:

```text
/导入最近
/导入最近 2
```

Inspect progress after import:

```text
/进展
/尾巴 20
/刷新
```

Continue the imported session:

```text
/继续 按方案 A 推进，完成后等我确认
```

Plain text is treated like `/继续 <text>` when the current task is not waiting
for a guarded confirmation.

From the PC, expose the latest active Codex desktop session to the most recent
DingTalk user:

```powershell
.\scripts\adopt_current_codex_session.ps1
```

If no DingTalk user has contacted the service yet:

```powershell
.\scripts\adopt_current_codex_session.ps1 -UserId <dingtalk-sender-id>
```

## Commands

```text
/新任务 <项目路径> <目标>
/会话
/最近会话
/导入最近 [编号]
/切换 <编号>
/状态
/进展
/刷新
/尾巴 [数量]
/继续 <补充指令>
/暂停
/确认
/拒绝
/运行测试
/差异
/提交
```

`/提交` only prepares a guarded commit action. Send `/确认` to actually commit,
or `/拒绝` to cancel. Plain text never confirms a guarded action.

## Verification

Run before committing or pushing:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check scripts/dingtalk_stream_bridge.mjs
git diff --check
```

The project does not define `npm test`; the Node side currently only contains
the DingTalk Stream bridge, checked with `node --check`.
