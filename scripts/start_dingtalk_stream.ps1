param(
    [string]$ConfigPath = "config/local.toml",
    [string]$WebhookUrl = "http://127.0.0.1:8765/dingtalk/webhook"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$envJson = @"
from codex_remote_control.config import load_config
import json

config = load_config(r"$ConfigPath")
print(json.dumps({
    "client_id": config.dingtalk.client_id,
    "client_secret": config.dingtalk.client_secret,
    "gateway_token": config.dingtalk.gateway_token,
}, ensure_ascii=False))
"@ | .\.venv\Scripts\python.exe -

$dingtalk = $envJson | ConvertFrom-Json
if (-not $dingtalk.client_id -or -not $dingtalk.client_secret) {
    throw "Missing dingtalk.client_id or dingtalk.client_secret in $ConfigPath"
}

$env:DINGTALK_CLIENT_ID = $dingtalk.client_id
$env:DINGTALK_CLIENT_SECRET = $dingtalk.client_secret
$env:DINGTALK_GATEWAY_TOKEN = $dingtalk.gateway_token
$env:CODEX_REMOTE_DINGTALK_WEBHOOK_URL = $WebhookUrl

node .\scripts\dingtalk_stream_bridge.mjs
