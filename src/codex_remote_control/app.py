from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from codex_remote_control.config import AppConfig, load_config
from codex_remote_control.feishu import FeishuParseError, parse_feishu_event, verify_event
from codex_remote_control.router import ConversationRouter
from codex_remote_control.store import TaskStore


def create_app(config: AppConfig | None = None) -> FastAPI:
    app_config = config or load_config(Path("config/local.toml"))
    store = TaskStore(app_config.storage.sqlite_path)
    router = ConversationRouter(app_config, store)
    app = FastAPI(title="Codex Remote Control")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/feishu/webhook")
    async def feishu_webhook(payload: dict) -> dict[str, str]:
        try:
            event = parse_feishu_event(payload)
        except FeishuParseError as error:
            return {"text": f"invalid feishu event: {error}"}
        verified = verify_event(event, app_config)
        if not verified.allowed:
            return {"text": verified.reason}
        return {"text": router.handle(verified.user_id, verified.text)}

    return app
