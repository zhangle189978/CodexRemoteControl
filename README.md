# Codex Remote Control

Windows-local chat gateway for controlled Codex coding tasks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install
pytest
ruff check .
```

## Configuration

Copy the example file:

```powershell
Copy-Item config/local.example.toml config/local.toml
```

Fill:

- `feishu.app_id`
- `feishu.app_secret`
- `feishu.verification_token`
- `feishu.allowed_user_ids`
- `dingtalk.gateway_token`
- `dingtalk.allowed_user_ids` after you know your DingTalk sender id
- `workspace.root`
- `workspace.default_test_command`

Never commit `config/local.toml`.

## Run

### Feishu or HTTP callback mode

```powershell
uvicorn codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

Expose one of these URLs through a local tunnel during development, then
configure the public URL in the chat bot:

- `http://127.0.0.1:8765/feishu/webhook`
- `http://127.0.0.1:8765/dingtalk/webhook`

### DingTalk Stream mode

DingTalk Stream mode does not need a public tunnel. Start the Python service in
one terminal:

```powershell
.\.venv\Scripts\uvicorn.exe codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

Then start the Stream bridge in another terminal:

```powershell
.\scripts\start_dingtalk_stream.ps1
```

The bridge reads DingTalk credentials from ignored `config/local.toml`, forwards
inbound messages to the local webhook, and sends text replies back through the
DingTalk robot API.

## Codex Session Handoff

From DingTalk, list recent Codex desktop sessions:

```text
/最近会话
```

Import the newest session, or a numbered item from the recent list:

```text
/导入最近
/导入最近 2
```

After importing, send `/继续 <message>` or plain text. Imported Codex sessions
are resumed with `codex exec resume <session-id> <message>`, so the work
continues against the original Codex session record and the final response is
sent back to DingTalk.

From the PC side, expose the latest Codex desktop session to the last DingTalk
user that messaged the bridge:

```powershell
.\scripts\adopt_current_codex_session.ps1
```

If no DingTalk user has messaged the bridge yet, pass the user id explicitly:

```powershell
.\scripts\adopt_current_codex_session.ps1 -UserId <dingtalk-sender-id>
```

## Supported Commands

```text
/新任务 <项目路径> <目标>
/会话
/最近会话
/导入最近 [编号]
/切换 <编号>
/状态
/继续 <补充指令>
/暂停
/确认
/拒绝
/运行测试
/差异
/提交
```

Commit requires `/提交` followed by `/确认`. Ordinary text never confirms a
release action.
