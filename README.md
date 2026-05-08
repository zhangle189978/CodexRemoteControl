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
- Continue imported Codex sessions by injecting text into the active Codex
  Desktop GUI, with app-server and CLI resume as fallbacks.
- Read imported session progress, tail events, assistant replies, and command
  results from Codex rollout records.
- Require explicit confirmation for release actions such as commit.

## Current Limitation

For imported Codex desktop sessions, `/继续 ...` now prefers GUI injection. The
Codex Desktop window must be open, visible, idle, and on the session you want to
control. If GUI injection cannot run, the bridge falls back to the experimental
app-server path, then to CLI resume.

GUI injection controls the current visible desktop session. After injecting a
message, the bridge waits for the next assistant reply or Codex error recorded
in that session and returns it to DingTalk. If no reply is recorded before the
wait timeout, use `/进展` or `/尾巴 20` to inspect the resulting rollout events.

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

## GUI Injection

To test GUI handoff manually, keep the Codex Desktop window open and idle:

```powershell
.\scripts\inject_codex_gui.ps1 -ListWindows
.\scripts\inject_codex_gui.ps1 "GUI_POC_OK" -NoSubmit -InputMode SendKeys
.\scripts\inject_codex_gui.ps1 "请只回复 GUI_POC_OK" -InputMode SendKeys
```

Expected result:

- The text is typed into the active Codex Desktop input.
- The send button is clicked automatically.
- The current GUI conversation executes the message.
- The assistant reply appears in the GUI and can later be read from the rollout
  file for DingTalk reply forwarding.

Use `-NoSubmit` to type without clicking send:

```powershell
.\scripts\inject_codex_gui.ps1 "draft text" -NoSubmit
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
