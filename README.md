# Codex Remote Control

Windows-local Feishu gateway for controlled Codex coding tasks.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```

## Local Run

Copy `config/local.example.toml` to `config/local.toml`, fill local values, then run:

```powershell
uvicorn codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```
