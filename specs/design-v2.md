# 智能日报生成器 · 迭代二：架构设计（design-v2）

> 本文档仅描述迭代二的**增量设计与接口契约**，未涉及内容沿用 [design.md](file:///d:/智能日报生成器/智能日报生成器/specs/design.md)。
> 依赖方向不变：`webapp → shared`；`collector/generator/notifier` 不依赖 `webapp`。

## 1. 模块总览

| 模块 | 职责 | 不负责 |
|---|---|---|
| `shared/models.py`（改） | `DailyReport` 新增 `failed_sources: list[str]` | — |
| `shared/serializer.py`（新） | `DailyReport` → 看板 JSON 字典 | HTML 转义、模板 |
| `shared/storage.py`（改） | `data_json` 列幂等迁移；随报告写入/读取 | 序列化格式定义 |
| `webapp/dashboard.html`（新） | 看板模板（由 Open Design 原型改造，占位符替换数据） | 数据获取（静态注入除外） |
| `webapp/export.py`（新） | 占位符替换、静态导出 HTML | HTTP |
| `webapp/server.py`（新） | 只读 HTTP 服务（页面 + `/api/reports`） | 写操作、鉴权 |
| `main.py`（改） | `--view` 升级、`--serve` 新增；管道传递 `failed_sources` | — |

## 2. 数据模型变更

```python
@dataclass(slots=True)
class DailyReport:
    date: date
    team_name: str
    members: list[MemberReport] = field(default_factory=list)
    generated_at: datetime | None = None
    markdown: str = ""
    html: str = ""
    failed_sources: list[str] = field(default_factory=list)  # 新增：如 ["github"]
```

管道约定：`failed_sources` 元素取自固定集合 `{"github", "lark_task", "lark_message"}`。

## 3. 序列化契约（shared/serializer.py）

```python
def report_to_dict(report: DailyReport) -> dict
```

输出结构（前端契约，字段名与看板 JS 严格一致）：

```json
{
  "date": "2026-09-26",
  "team_name": "研发一组",
  "generated_at": "18:02",
  "failed_sources": [],
  "members": [
    {
      "name": "刘政剑",
      "github_username": "chenpingan6158-a11y",
      "commits": [
        {"repo": "usermanagersystem.github.io", "message": "...",
         "additions": 214, "deletions": 32, "files_changed": 6, "time": "10:24"}
      ],
      "tasks": [
        {"title": "...", "status_from": "进行中", "status_to": "已完成", "time": "15:10"}
      ],
      "messages": [
        {"chat_name": "SDD测试", "content": "...", "time": "11:02"}
      ]
    }
  ]
}
```

规则：

- 所有时间统一格式化为运行环境本地时区 `HH:MM`（复用一期 `formatter._hhmm` 的本地时区逻辑，序列化器内独立实现，避免 webapp→generator 反向依赖）；
- `MemberReport.github_username` 为空串时输出 `null`；
- 成员顺序、各记录顺序与内存对象一致；
- JSON 序列化统一 `ensure_ascii=False`。

## 4. 存储迁移契约（shared/storage.py）

- 初始化时查询 `PRAGMA table_info(reports)`；若无 `data_json` 列，执行
  `ALTER TABLE reports ADD COLUMN data_json TEXT NOT NULL DEFAULT ''`（SQLite 支持，幂等）；
- `save_report` 写入 `data_json = json.dumps(report_to_dict(report), ensure_ascii=False)`，upsert 时同步更新；
- `get_report` 返回行包含 `data_json`（可能为空串）；
- 新增 `iter_report_data(limit: int = 30) -> list[dict]`：`SELECT data_json FROM reports WHERE data_json <> '' ORDER BY date DESC, id DESC LIMIT ?`，返回解析后的字典列表（看板的历史来源）。

一期遗留行 `data_json = ''`，在看板中静默缺失，不报错。

## 5. 看板模板（webapp/dashboard.html）

在 Open Design 原型基础上做最小改造，视觉与交互不变：

| 原型内容 | 替换为 |
|---|---|
| `var REPORTS = [ ...硬编码... ];` | `var REPORTS = __REPORTS_JSON__;`（静态导出为数组字面量；服务模式为 `null`） |
| `var state = { date: REPORTS[0].date, ...` | `date: __INITIAL_DATE__ || REPORTS[0].date`（静态导出指定日期时为 `"YYYY-MM-DD"`，否则 `null`） |

启动逻辑：`REPORTS === null` 时 `fetch('api/reports')` 取数赋值后再 `renderAll()`；其余渲染逻辑不变。页脚"原型/示例数据"文案删除。

## 6. 静态导出契约（webapp/export.py）

```python
def render_dashboard(reports: list[dict], initial_date: str | None = None) -> str
def export_dashboard(reports, out_path: str | Path, initial_date=None) -> Path
```

- 仅做两处占位符的字符串替换；JSON 注入前对 `</script` 序列做转义（`<\/script`），防止内容截断脚本；
- 导出路径沿用 `data/` 目录：无指定日期 → `data/dashboard.html`；指定日期 → `data/report-<date>.html`。

## 7. HTTP 服务契约（webapp/server.py）

```python
def serve(config: Config, *, host: str = "127.0.0.1", port: int = 0,
          open_browser: bool = True) -> None
```

基于 `ThreadingHTTPServer` + `BaseHTTPRequestHandler`：

| 方法 & 路径 | 响应 |
|---|---|
| `GET /`、`GET /index.html` | dashboard.html，以 `REPORTS=null` 渲染（`Content-Type: text/html; charset=utf-8`） |
| `GET /api/reports` | `{"code": 0, "reports": [...]}`，数据每次实时读 SQLite；支持可选 `?date=YYYY-MM-DD` 过滤单篇 |
| 其他 | `404` + `{"code": 404, "msg": "not found"}` |

约束：

- 仅绑定 `127.0.0.1`；`port=0` 时由系统分配，启动后打印实际地址并自动打开浏览器；
- 服务为只读：除 GET 外方法返回 `405`；
- 每个请求独立打开/关闭 `ReportStorage`（低频本地调用，无需连接池）。

## 8. CLI 变更（main.py）

- `--view [date]`：从 `storage.iter_report_data()` 取数；空列表时打印提示并返回非零；否则 `export_dashboard` 后打开浏览器；
- `--serve`：加载配置后进入 `serve()`，由 Ctrl+C 正常退出（捕获 `KeyboardInterrupt`，退出码 0）；
- 管道：`DailyReport` 构造时传入 `failed_sources`。

## 9. 测试策略

| 对象 | 方式 |
|---|---|
| serializer | 固定 `DailyReport` 快照，断言字段、`null` 映射、时间格式 |
| storage 迁移 | 先建旧 schema 写一期格式数据 → 用 `ReportStorage` 打开 → 列存在、旧行可读且 `data_json==''`、新写入可解析 |
| export | 断言占位符被替换、`</script>` 转义、输出可解析 |
| server | 真实启动于 `127.0.0.1:0`，httpx 校验 `/`、`/api/reports`、`?date=`、404、405；测试结束关闭 |
| CLI | `--view`（有/无数据）、`--serve` 冒烟 |
