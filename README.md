# Codex Remote Control

本项目是在 Windows 本机运行的 Codex 远程控制网关。目标是让你在 PC 端启动 Codex 编程任务后，可以通过钉钉或飞书在手机上查看进展、切换会话、补充指令，并在需要确认时继续推进。

## 当前能力

- 飞书 HTTP Webhook 接入。
- 钉钉 HTTP Webhook 接入。
- 钉钉 Stream 模式接入，不需要公网隧道。
- 远程创建、切换、暂停、继续本地任务。
- 导入最近的 Codex 桌面会话，并用 `codex exec resume <session-id>` 继续原会话。
- 查看导入会话的最新进展、尾部事件和命令执行结果。
- commit 等 release 动作必须二次确认，普通文本不会误触发。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm install
```

## 配置

复制示例配置：

```powershell
Copy-Item config/local.example.toml config/local.toml
```

填写必要字段：

- `feishu.app_id`
- `feishu.app_secret`
- `feishu.verification_token`
- `feishu.allowed_user_ids`
- `dingtalk.gateway_token`
- `dingtalk.allowed_user_ids`
- `workspace.root`
- `workspace.default_test_command`

不要提交 `config/local.toml`。

## 运行

### 飞书或 HTTP 回调模式

```powershell
.\.venv\Scripts\uvicorn.exe codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

开发期通过本地隧道暴露下面其中一个地址，再配置到机器人后台：

- `http://127.0.0.1:8765/feishu/webhook`
- `http://127.0.0.1:8765/dingtalk/webhook`

### 钉钉 Stream 模式

钉钉 Stream 模式不需要公网隧道。先启动本地 Python 服务：

```powershell
.\.venv\Scripts\uvicorn.exe codex_remote_control.app:create_app --factory --host 127.0.0.1 --port 8765
```

再启动钉钉 Stream 桥接进程：

```powershell
.\scripts\start_dingtalk_stream.ps1
```

桥接进程会读取 `config/local.toml` 里的钉钉配置，把钉钉消息转发到本地 webhook，并把本地回复发回钉钉机器人。

## Codex 会话接管

手机端查看最近 Codex 桌面会话：

```text
/最近会话
```

导入最新会话或指定编号：

```text
/导入最近
/导入最近 2
```

导入后可以查看进展：

```text
/进展
/尾巴 20
/刷新
```

- `/进展`：读取当前导入 Codex 会话的最新关键消息、助手回复和命令结果。
- `/尾巴 [数量]`：读取最近 N 条关键事件，默认 20 条。
- `/刷新`：重新读取最新进展，并写回当前导入任务的摘要。

继续原 Codex 会话：

```text
/继续 按方案 A 继续实现，完成后等我确认
```

也可以直接发普通文本；只要当前任务没有等待 release 确认，普通文本等价于 `/继续 <文本>`。

PC 端可以把最新 Codex 桌面会话主动暴露给最近一个钉钉用户：

```powershell
.\scripts\adopt_current_codex_session.ps1
```

如果还没有钉钉用户给桥接服务发过消息，显式传入用户 id：

```powershell
.\scripts\adopt_current_codex_session.ps1 -UserId <dingtalk-sender-id>
```

## 支持命令

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

`/提交` 只会准备 release 动作，必须继续发送 `/确认` 才会真正 commit。发送普通文本不会确认 release 动作。

## 验证

提交前运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check scripts/dingtalk_stream_bridge.mjs
git diff --check
```

项目没有定义 `npm test`。Node 侧当前只有钉钉 Stream 桥接脚本，使用 `node --check` 做语法验证。
