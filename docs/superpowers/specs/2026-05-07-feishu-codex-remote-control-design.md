# Feishu Codex Remote Control Design

## 背景

用户经常在离开电脑后仍希望继续推进 Codex 编程任务。第一版目标不是远程桌面，也不是开放任意终端，而是在飞书中提供一个受控的远程任务控制台，让本机 Windows 电脑继续承担代码读取、修改、测试和汇报工作。

本项目是独立新仓库，路径为 `C:\Users\89493\Documents\CodexRemoteControl`。第一版优先接入飞书机器人，运行方式为本机常驻服务。

## 目标

MVP 需要支持以下能力：

- 通过飞书机器人创建、切换和继续 Codex 编程任务。
- 在本机 Windows 环境中绑定具体 workspace 执行代码分析、修改和测试。
- 支持任务级接续：保存任务摘要、状态、最近决策和等待确认事项。
- 预留真实 Codex session 适配层，未来可升级为真实会话切换。
- 允许机器人触发代码修改和测试。
- 对 commit、push、PR 等外部可见动作强制二次确认。
- 保存操作日志，支持查询当前任务状态。

## 非目标

第一版不做以下内容：

- 不做完整远程桌面控制。
- 不开放任意 shell 直通。
- 不同时接入钉钉。
- 不做多用户权限系统，只支持用户 ID 白名单。
- 不做 Web 管理后台。
- 不保证真实复用 Codex 桌面 App 当前 thread。
- 不自动 commit、push 或创建 PR。

## 推荐架构

```text
Feishu Bot
  -> Local Gateway Service
  -> Auth & Signature Verification
  -> Conversation Router
  -> Task Store
  -> Task Runner
  -> Codex Adapter
  -> Workspace Executor
  -> Feishu Reply/Callback
```

### Local Gateway Service

本机常驻 HTTP 服务，运行在 Windows 电脑上，接收飞书机器人 Webhook。开发期可通过内网穿透暴露到公网；正式使用时仍要求飞书验签和用户白名单双重校验。

职责：

- 接收飞书消息事件。
- 校验飞书签名和消息来源。
- 将消息转换为内部命令或普通任务输入。
- 将执行结果回推到飞书。

### Auth & Signature Verification

所有飞书事件必须通过验签。除飞书平台验签外，服务还维护允许使用机器人的飞书用户 ID 白名单。

安全规则：

- 未通过验签的请求直接拒绝。
- 不在白名单内的用户只能收到拒绝消息。
- release 级动作必须绑定 pending confirmation，不能由普通消息误触发。

### Conversation Router

会话路由器维护“当前选中的任务”。用户可以通过 `/会话` 查看任务列表，通过 `/切换 <编号>` 切换当前任务。未显式指定任务的普通消息会进入当前任务。

职责：

- 解析 slash command。
- 为每个用户维护当前任务指针。
- 将 `/继续 <补充指令>` 和普通消息路由到当前任务。
- 在任务等待确认时，将 `/确认` 或 `/拒绝` 路由给 pending action。

### Task Store

任务存储保存任务状态、摘要和审计日志。第一版推荐使用 SQLite，而不是纯 JSON 文件，因为 SQLite 更适合后续按任务、workspace、状态、时间查询。

核心数据：

- task id
- display title
- workspace path
- branch or worktree path
- permission level
- status
- current summary
- last user instruction
- pending confirmation
- created at / updated at
- operation log

任务状态：

```text
created
running
waiting_confirmation
paused
failed
completed
```

### Task Runner

任务运行器负责串行执行单个任务中的工作，避免同一个 workspace 同时被多个任务改写。

职责：

- 接收任务输入。
- 检查 workspace 白名单和任务权限。
- 调用 Codex Adapter。
- 调用 Workspace Executor 跑测试或查看 diff。
- 捕获错误并写入日志。
- 将阶段性进展推送到飞书。

### Codex Adapter

Codex Adapter 是后续演进的关键边界。第一版采用混合会话策略：不强依赖真实 Codex session，而是把任务摘要、最近变更和用户新指令组织为一次 Codex 执行输入。

接口需要表达以下能力：

- start task
- continue task
- summarize task
- request status
- handle confirmation result

第一版实现可以调用本机可用的 Codex CLI 或封装命令。适配器不得暴露任意 shell 给飞书消息。

未来如果 Codex 提供稳定 session API，只替换 Codex Adapter，不重写飞书入口、任务存储和权限模型。

### Workspace Executor

Workspace Executor 执行受控的本地 workspace 操作。它只允许在配置白名单内工作。

第一版允许的动作：

- 读取 git status。
- 获取 diff 摘要。
- 运行配置好的测试命令。
- 配合 Codex Adapter 修改代码。
- 在确认后执行 git commit。

第一版禁止的动作：

- 任意 shell 命令。
- 未确认的 commit、push、PR。
- 修改白名单外路径。
- 删除 workspace 或执行破坏性 git 操作。

## 权限模型

任务权限分为三档：

```text
read     查看状态、读取摘要、查询 git 状态和 diff 摘要
work     允许修改代码、运行测试、生成 diff
release  允许 commit / push / PR，但必须二次确认
```

MVP 默认任务权限为 `work`。`release` 动作即使任务具备权限，也必须进入 `waiting_confirmation` 状态，等待用户回复 `/确认`。

## 飞书指令

MVP 支持以下指令：

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

普通文本消息规则：

- 如果当前任务存在且未等待确认，普通文本等价于 `/继续 <文本>`。
- 如果当前任务等待确认，普通文本不会默认确认 release 动作，必须使用 `/确认`。
- 如果没有当前任务，提示用户使用 `/新任务` 或 `/会话`。

## 关键工作流

### 新建并推进任务

```text
用户：/新任务 C:\Users\89493\Documents\HollyDB 修复 xxx
系统：校验用户、校验 workspace 白名单、创建任务
系统：开始分析并回推阶段状态
系统：修改代码并运行测试
系统：回推改动文件、测试结果和下一步建议
```

### 切换任务

```text
用户：/会话
系统：
1. HollyDB 修复 xxx - running
2. Playground 前端调整 - paused

用户：/切换 1
系统：已切换到 HollyDB 修复 xxx
```

### 提交代码

```text
用户：/提交
系统：展示拟提交文件、提交说明、测试结果，进入 waiting_confirmation
用户：/确认
系统：执行 git commit，回推 commit hash
```

## 配置

第一版配置文件建议使用 `config/local.toml`，不提交真实密钥。仓库提供 `config/local.example.toml`。

配置项：

- 飞书 app id
- 飞书 app secret
- 飞书 verification token 或 encrypt key
- 允许的飞书用户 ID
- 允许的 workspace 根路径
- 每个 workspace 的默认测试命令
- Codex CLI 路径或适配器命令
- 本机服务监听端口

## 错误处理

错误处理原则：

- 对用户返回短摘要，不推送长日志。
- 长日志写入本地操作日志。
- workspace 不在白名单内时拒绝执行。
- Codex 执行失败时保留任务状态和错误摘要。
- 测试失败不自动回滚，回推失败摘要和相关文件。
- release 动作确认过期后必须重新发起。

## 测试策略

MVP 测试覆盖重点：

- 飞书命令解析。
- 用户白名单校验。
- workspace 白名单校验。
- 会话切换和当前任务路由。
- waiting confirmation 状态机。
- release 动作不能被普通文本误确认。
- Task Store 持久化和恢复。
- Workspace Executor 禁止白名单外路径。

第一版可用单元测试覆盖核心状态机和命令解析；飞书 Webhook 使用本地 fixture 做集成测试。

## 实施顺序

建议分阶段实现：

1. 项目脚手架、配置加载、基础日志。
2. 飞书 Webhook 接收、验签和用户白名单。
3. 命令解析和 Conversation Router。
4. SQLite Task Store。
5. Task Runner 状态机。
6. Workspace 白名单、git status、diff、测试命令。
7. Codex Adapter 最小实现。
8. `/提交` 和 `/确认` release 流程。
9. 本地运行文档和飞书配置说明。

## 成功标准

MVP 完成时，应能在飞书中完成以下闭环：

- 创建一个绑定本机 workspace 的任务。
- 从飞书继续给任务追加指令。
- 系统能在本机修改代码并运行测试。
- 用户能查询状态、查看 diff 摘要、切换任务。
- 提交前系统会请求确认，只有 `/确认` 后才执行 commit。
- 服务重启后，任务列表和当前任务状态仍可恢复。
