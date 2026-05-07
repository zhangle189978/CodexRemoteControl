# Codex Remote Control

Windows-local Feishu gateway for controlled Codex coding tasks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
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
- `workspace.root`
- `workspace.default_test_command`

Never commit `config/local.toml`.

## Run

```powershell
uvicorn codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

Expose `http://127.0.0.1:8765/feishu/webhook` through a local tunnel during
development, then configure that public URL in the Feishu bot.

## Supported Commands

```text
/新任务 <项目路径> <目标>
/会话
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
