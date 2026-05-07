from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class FeishuConfig:
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    allowed_user_ids: frozenset[str]


@dataclass(frozen=True)
class DingtalkConfig:
    enabled: bool
    client_id: str
    client_secret: str
    gateway_token: str
    gateway_password: str
    require_mention: bool
    group_policy: str
    group_session_scope: str
    allowed_user_ids: frozenset[str]


@dataclass(frozen=True)
class StorageConfig:
    sqlite_path: Path


@dataclass(frozen=True)
class CodexConfig:
    command: str


@dataclass(frozen=True)
class WorkspaceConfig:
    name: str
    root: Path
    default_test_command: str


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    feishu: FeishuConfig
    dingtalk: DingtalkConfig
    storage: StorageConfig
    codex: CodexConfig
    workspaces: tuple[WorkspaceConfig, ...]

    @classmethod
    def for_tests(
        cls,
        allowed_user_ids: list[str] | None = None,
        workspace_roots: list[Path] | None = None,
    ) -> AppConfig:
        roots = workspace_roots or []
        return cls(
            server=ServerConfig(host="127.0.0.1", port=8765),
            feishu=FeishuConfig(
                app_id="cli_test",
                app_secret="secret",
                verification_token="token",
                encrypt_key="",
                allowed_user_ids=frozenset(
                    ["ou_allowed"] if allowed_user_ids is None else allowed_user_ids
                ),
            ),
            dingtalk=DingtalkConfig(
                enabled=True,
                client_id="ding_test",
                client_secret="secret",
                gateway_token="ding_token",
                gateway_password="",
                require_mention=True,
                group_policy="open",
                group_session_scope="group",
                allowed_user_ids=frozenset(),
            ),
            storage=StorageConfig(sqlite_path=Path(":memory:")),
            codex=CodexConfig(command="codex"),
            workspaces=tuple(
                WorkspaceConfig(
                    name=root.name,
                    root=root.resolve(),
                    default_test_command="pytest",
                )
                for root in roots
            ),
        )

    def workspace_by_name(self, name: str) -> WorkspaceConfig:
        for workspace in self.workspaces:
            if workspace.name == name:
                return workspace
        raise KeyError(name)

    def is_allowed_workspace(self, candidate: str | Path) -> bool:
        resolved = Path(candidate).resolve()
        return any(_is_relative_to(resolved, workspace.root) for workspace in self.workspaces)


def _is_relative_to(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(config_path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.resolve().parent
    dingtalk = raw.get("dingtalk", {})
    return AppConfig(
        server=ServerConfig(**raw["server"]),
        feishu=FeishuConfig(
            app_id=raw["feishu"]["app_id"],
            app_secret=raw["feishu"]["app_secret"],
            verification_token=raw["feishu"]["verification_token"],
            encrypt_key=raw["feishu"].get("encrypt_key", ""),
            allowed_user_ids=frozenset(raw["feishu"]["allowed_user_ids"]),
        ),
        dingtalk=DingtalkConfig(
            enabled=dingtalk.get("enabled", False),
            client_id=dingtalk.get("client_id", ""),
            client_secret=dingtalk.get("client_secret", ""),
            gateway_token=dingtalk.get("gateway_token", ""),
            gateway_password=dingtalk.get("gateway_password", ""),
            require_mention=dingtalk.get("require_mention", True),
            group_policy=dingtalk.get("group_policy", "open"),
            group_session_scope=dingtalk.get("group_session_scope", "group"),
            allowed_user_ids=frozenset(dingtalk.get("allowed_user_ids", [])),
        ),
        storage=StorageConfig(
            sqlite_path=_resolve_from_base(base_dir, Path(raw["storage"]["sqlite_path"]))
        ),
        codex=CodexConfig(command=raw["codex"]["command"]),
        workspaces=tuple(
            WorkspaceConfig(
                name=item["name"],
                root=Path(item["root"]).resolve(),
                default_test_command=item["default_test_command"],
            )
            for item in raw.get("workspace", [])
        ),
    )


def _resolve_from_base(base_dir: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()
