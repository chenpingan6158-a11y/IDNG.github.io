# 智能日报生成器 — 架构设计

> SDD 阶段二、三产物：架构设计 + 接口契约（design.md）——回答"用什么结构解决"。
> 本文档严格在 proposal.md 的约束下展开：不新增 proposal.md 未授权的能力。

## 1. 系统架构

- **架构模式**：管道式架构（Pipeline Architecture）。数据具有明确的线性、同步流向（输入→处理→输出），各阶段职责清晰且独立。
- **分层**：采集层 → 生成层 → 推送层，外加跨层共享基础层。
- **选型理由**：proposal.md 已界定"5 人团队规模""不需要常驻服务"，引入微服务徒增复杂性；不存在复杂事件分发与异步解耦需求，故不采用事件驱动架构。遵循"选择能满足需求的最简架构"。

```text
┌────────────┐     ┌────────────┐     ┌────────────┐
│  采集层     │ --> │  生成层     │ --> │  推送层     │
│ Collector  │     │ Generator  │     │ Notifier   │
└─────┬──────┘     └────────────┘     └──────┬─────┘
      │                                      │
      └──────────────┬───────────────────────┘
                     ▼
        ┌──────────────────────────┐
        │       共享基础层          │
        │ 配置管理 | 日志 | 错误处理 │
        │         | 数据存储        │
        └──────────────────────────┘

数据流向：
GitHub API / 飞书任务 API / 飞书消息 API
        → 采集层 → 原始数据(JSON)
        → 生成层 → 日报(Markdown/HTML)
        → 推送层 → 邮件 + 飞书消息
```

## 2. 模块职责

| 模块 | 负责 | 不负责 |
|------|------|--------|
| `collector/github.py` | 从 GitHub API 获取仓库 Commit 数据 | 不做数据格式化、不做去重判断、不做推送 |
| `collector/lark_task.py` | 从飞书开放平台获取任务状态变更数据 | 不做数据格式化、不做去重判断、不做推送 |
| `collector/lark_msg.py` | 从飞书群获取消息并按关键词过滤 | 不做数据格式化、不做去重判断、不做推送 |
| `generator/formatter.py` | 数据整理、聚合、Markdown 生成 | 不做数据采集、不做 API 调用、不做推送 |
| `generator/template.py` | 日报模板（Jinja2）管理、HTML 渲染 | 不做数据采集、不做 API 调用、不做推送 |
| `notifier/email.py` | 通过 SMTP 发送 HTML 格式日报 | 不做数据处理、不做日报生成、不做数据采集 |
| `notifier/lark_bot.py` | 通过飞书机器人 webhook 推送 Markdown 日报 | 不做数据处理、不做日报生成、不做数据采集 |
| `shared/config.py` | 配置读取与校验 | — |
| `shared/logger.py` | 统一 JSON lines 日志格式 | — |
| `shared/errors.py` | 自定义异常与错误处理策略 | — |
| `shared/storage.py` | SQLite 日报历史存储 | — |
| `main.py` | 编排入口：按顺序调用三层、处理全局异常、记录执行状态 | 不实现任何具体业务逻辑 |

模块划分遵循单一职责原则（SRP）与关注点分离（SoC）：每个模块仅有一个引发变更的理由。

### 成员身份映射

GitHub 用户名与飞书用户名属于不同命名空间，必须在配置文件中维护映射表，使三个数据源的数据能按"人"聚合：

```yaml
members:
  - name: "张三"
    github: "zhangsan"
    lark: "zhangsan@company.com"
  - name: "李四"
    github: "lisi-dev"
    lark: "lisi@company.com"
  - name: "王五"
    github: "wangwu"
    lark: "wangwu@company.com"
```

## 3. 数据模型

只承载语义，不绑定实现（dataclass / Pydantic / NamedTuple 由实现阶段自由裁量）。

### CommitRecord（代码提交记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| author | str | 提交者（GitHub 用户名） |
| message | str | 提交信息（Commit Message） |
| timestamp | datetime | 提交时间 |
| repo | str | 仓库名称 |
| additions | int | 新增行数 |
| deletions | int | 删除行数 |
| files_changed | int | 变更文件数 |

### TaskRecord（任务变更记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| assignee | str | 负责人（飞书用户名） |
| title | str | 任务标题 |
| status_from | str | 原状态 |
| status_to | str | 新状态 |
| updated_at | datetime | 变更时间 |

### MessageRecord（消息记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| sender | str | 发送者（飞书用户名） |
| content | str | 消息内容（纯文本） |
| timestamp | datetime | 发送时间 |
| chat_name | str | 群名称 |

### MemberReport（成员报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | str | 成员姓名 |
| github_username | str | GitHub 用户名 |
| commits | list[CommitRecord] | 代码提交记录 |
| tasks | list[TaskRecord] | 任务变更记录 |
| messages | list[MessageRecord] | 相关消息记录 |

### DailyReport（每日报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| date | date | 日报日期 |
| team_name | str | 团队名称 |
| members | list[MemberReport] | 各成员的日报段落 |
| generated_at | datetime | 生成时间 |
| markdown | str | 完整的 Markdown 格式日报 |
| html | str | 完整的 HTML 格式日报 |

## 4. 接口契约

### 4.1 采集层接口

```python
github.collect(
    repos: list[str],        # 仓库列表
    since: datetime,         # 起始时间
    until: datetime          # 结束时间
) -> list[CommitRecord]      # 返回提交记录列表

lark_task.collect(
    project_id: str,         # 飞书项目 ID
    since: datetime,         # 起始时间
    until: datetime          # 结束时间
) -> list[TaskRecord]        # 返回任务变更列表

lark_msg.collect(
    chat_id: str,            # 群 ID
    keywords: list[str],     # 过滤关键词
    since: datetime,        # 起始时间
    until: datetime          # 结束时间
) -> list[MessageRecord]     # 返回消息记录列表
```

### 4.2 生成层接口

```python
generator.generate(
    members: list[MemberReport],  # 各成员数据
    date: date,                   # 日报日期
    team_name: str                # 团队名称
) -> DailyReport                  # 返回日报
```

### 4.3 推送层接口

```python
email.send(
    report: DailyReport,      # 日报对象
    recipients: list[str]     # 收件人邮箱列表
) -> bool                     # 成功/失败

lark_bot.send(
    report: DailyReport,      # 日报对象
    chat_id: str              # 目标群 ID
) -> bool                     # 成功/失败
```

## 5. 技术选型（ADR）

### ADR-001：使用 httpx 作为 HTTP 客户端

**状态**：已采纳

**背景**：智能日报生成器需要调用多个外部 API（如 GitHub API、飞书开放平台 API）来获取数据，需要选择一个稳定、高效的 HTTP 客户端库。

**选项**：

| 选项 | 优点 | 缺点 |
|------|------|------|
| requests | 社区最广泛，文档丰富，团队熟悉 | 不支持原生异步，连接池管理较弱 |
| httpx | 同时支持同步和异步，API 兼容 requests，支持 HTTP/2 | 相对较新，部分边缘场景文档不足 |
| aiohttp | 成熟的异步 HTTP 库 | 仅支持异步，API 风格与 requests 差异大 |

**决策**：使用 httpx

**理由**：

1. proposal.md 明确要求"5 人团队日报生成 < 60s"，且三个数据源可并发采集，异步能力是实现性能目标的关键。
2. httpx 的同步 API 与 requests 几乎完全一致，团队迁移成本极低。
3. 采集层当前使用同步模式，未来可平滑切换至异步模式，不需要重写代码。
4. 不选择 aiohttp，因为我们不需要强制异步——在同步模式下程序也必须能正常运行。

### ADR-002：使用 SQLite 存储日报历史

**状态**：已采纳

**背景**：虽然 proposal.md 明确要求"数据存储：本地 SQLite"，但为确保架构合理性，需对该选择进行正式评估。

**选项**：

| 选项 | 优点 | 缺点 |
|------|------|------|
| SQLite | 零部署、零运维、Python 内置支持、文件级备份 | 不支持高并发写入、数据量极大时查询性能下降 |
| PostgreSQL | 功能完整、支持高并发、强大的全文搜索能力 | 需要独立部署和运维，对 5 人团队日报场景过于沉重 |
| JSON 文件 | 实现最简单、不需要任何依赖 | 缺乏复杂查询能力、并发写入不安全、数据量增长后难以管理 |

**决策**：使用 SQLite

**理由**：

1. proposal.md 明确运行方式为"人工手动触发，不需要常驻服务"，不存在并发写入场景（单次执行、串行写入）。
2. 5 人团队一年的日报数据约为 1250 条，SQLite 处理起来绰绰有余。
3. 零运维高度符合项目定位——不想为一个简单的日报工具维护独立的数据库服务。
4. Python 标准库 sqlite3 开箱即用，不需要引入额外的第三方依赖。

## 6. 非功能性约束

### 6.1 错误处理：优雅降级（Graceful Degradation）

| 场景 | 处理方式 |
|------|----------|
| GitHub API 超时 | 重试 3 次（间隔 5s），若仍失败则标记"数据获取失败" |
| 飞书 Token 过期 | 自动刷新 Token 后重试 1 次 |
| 单个数据源完全不可用 | 跳过该数据源，日报中标注"XX 数据源暂不可用"，其他数据源正常采集 |
| 所有数据源都不可用 | 记录错误日志，发送告警邮件，不生成空日报 |
| 邮件发送失败 | 重试 2 次，若仍失败则记录日志和飞书消息告警 |
| 飞书推送失败 | 重试 2 次，若仍失败则记录日志和邮件告警 |

关键原则：

1. 采集层的失败不应阻塞生成层。
2. 生成层的失败不应阻塞推送层（需要推送错误报告）。
3. 任何失败都必须有日志记录。
4. 推送渠道应互为备份告警通道。

### 6.2 安全约束

1. **密钥管理**
   - 所有 API 密钥均通过环境变量注入
   - 严禁在代码或配置文件中硬编码密钥
   - 加入 .env 文件，则必须加入 .gitignore
2. **数据安全**
   - 对飞书消息中的敏感关键词（如薪资、绩效、裁员等）进行过滤（配置黑名单）
   - 日报中不包含代码差异的具体内容（仅包含统计数据，如 +10 行 / -5 行）
3. **访问控制**
   - 仅采集配置文件中明确列出的仓库或群组
   - 不采集配置范围之外的任何数据

### 6.3 可运维性设计

1. **日志**
   - 格式：JSON lines（便于日志分析工具解析）
   - 级别：INFO（正常流程）+ ERROR（异常）
   - 每次执行记录：开始时间、结束时间、各数据源采集条数及推送结果
2. **健康检查**
   - 提供 `main.py --check` 模式：验证所有 API 连接、邮件配置、飞书机器人权限是否正常
   - 建议部署后定期手动执行一次
3. **配置热更新**
   - 成员映射表（config.yaml）修改后下次执行即可自动生效，不需要重启服务
   - 新增或删除成员时不需要修改代码
