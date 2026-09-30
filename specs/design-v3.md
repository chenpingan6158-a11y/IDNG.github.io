# 智能日报生成器 · 迭代三：看板自动刷新（design-v3）

> 状态：**已随 proposal-v3 批准进入实现**
> 日期：2026-09-30
> 依据：proposal-v3（F1~F4、验收标准、非目标）

## 1. 总体思路

不引入事件订阅，采用"**后台守护线程定时拉取 + 前端定时轮询 + 指纹比对**"：

```
serve 启动
 ├─ HTTP 服务（迭代二已有）
 └─ AutoCollector 守护线程
      ├─ 立即采集一次（dry-run 落库，不推送）
      └─ 每 interval 秒循环：采集 → 指纹变化由前端轮询发现 → 自动重渲染
```

线程协调用 `threading.Event`：间隔期可被 `stop()` 立即唤醒，测试不依赖 sleep 盲等。

## 2. 模块改动表

| 模块 | 改动 | 对应功能 |
|---|---|---|
| `main.py` | `run_pipeline` 新增 `force: bool = False`，为 True 时跳过工作日判断；`--run` 路径不传，语义不变 | F2、F4 |
| `webapp/server.py` | 新增 `auto_refresh_settings()`、`AutoCollector`；`render_served_page(interval)`；`build_server` 记录间隔；`serve` 接线启停 | F1、F2 |
| `webapp/dashboard.html` | 新增 `__AUTO_REFRESH_INTERVAL__` 占位符；动态模式启动轮询，指纹比对后重渲染并保留视图状态 | F3 |
| `webapp/export.py` | 静态导出将该占位符替换为 `0`（静态文件无后端，不轮询） | F3 |
| `tests/` | 新增 `test_auto_refresh.py`；扩展 test_export / test_server | 验收 4、5 |

## 3. 配置解析契约（F1）

`webapp/server.py`：

```python
DEFAULT_INTERVAL = 60
MIN_INTERVAL = 10

def auto_refresh_settings(config) -> tuple[bool, int]:
    section = ((config.get("dashboard") or {}).get("auto_refresh")) or {}
    enabled = bool(section.get("enabled", True))
    try:
        interval = int(section.get("interval_seconds", DEFAULT_INTERVAL))
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL
    return enabled, max(interval, MIN_INTERVAL)
```

- 入参兼容 `Config` 与普通 dict（测试构造用）；
- 缺段/缺字段 → `(True, 60)`；非法值 → 60；小于 10 → 钳制为 10；
- `enabled=False` 时服务行为与迭代二一致（不起线程、页面间隔为 0）。

## 4. 管道强制参数（F2/F4）

```python
def run_pipeline(config, *, now=None, dry_run=False, force=False) -> bool:
    ...
    if not force and not is_workday(today, config):
        ...  # 原有跳过逻辑
```

- 手动 `--run`：`force` 默认 False，非工作日仍跳过（F4 语义不变）；
- 自动采集：`run_pipeline(config, dry_run=True, force=True)`，任何日期都采集，且永不推送。

## 5. AutoCollector 契约（F2）

```python
class AutoCollector:
    def __init__(self, config, interval_seconds, *, collect_func=None): ...
    def start(self) -> None: ...   # 启动守护线程，幂等
    def stop(self) -> None: ...    # 唤醒等待并 join（≤5s）
```

行为：

1. 线程启动后**立即执行一次** `collect_func(config)`，再 `Event.wait(interval)` 循环；
2. 默认 `collect_func`：`from main import run_pipeline; run_pipeline(config, dry_run=True, force=True)`（函数内延迟导入，避免循环导入）；
3. 采集抛出**任何异常**都被捕获、经 logger 记录为 warning，循环继续；
4. `stop()` 设置 Event：若线程正处于等待则立即退出，正在采集则本轮结束后退出；
5. 线程为 daemon，主进程退出时不会被挂住。

## 6. HTTP 服务接线（F2）

- `build_server`：调用 `auto_refresh_settings(config)`，在 server 上记录
  `server.auto_refresh_enabled`、`server.auto_refresh_interval`；
- `render_served_page(interval_seconds)`：在迭代二两次替换之外，再把
  `__AUTO_REFRESH_INTERVAL__` 替换为数字字符串；
- handler 的 GET `/` 使用 `self.server.auto_refresh_interval`（每次请求实时渲染，改模板无需重启）；
- `serve`：

```python
collector = AutoCollector(config, interval) if enabled else None
if collector: collector.start()
try:
    server.serve_forever()
finally:
    if collector: collector.stop()
    server.shutdown(); server.server_close()
```

## 7. 前端轮询契约（F3）

模板脚本区新增全局：`var AUTO_REFRESH_INTERVAL = __AUTO_REFRESH_INTERVAL__;`

`boot()` 动态分支首次加载成功后：记录 `lastFingerprint = JSON.stringify(REPORTS)`，
调用 `startPolling()`（静态模式间隔为 0，直接 return）：

```text
每 AUTO_REFRESH_INTERVAL 秒：
  1. document.hidden 为真 → 跳过本轮
  2. fetch("api/reports") → reports
  3. fingerprint = JSON.stringify(reports)；与 lastFingerprint 相同 → 不做任何事
  4. 不同 → 更新 REPORTS/指纹；
     若 state.date 已不在新数据中 → state.date = REPORTS[0].date（最新一天）；
     state.member 原样保留；renderAll()
  5. fetch 失败 → 静默，等下一轮
```

顺序约定沿用迭代二：`iter_report_data` 按 `date DESC` 返回，`REPORTS[0]` 即最新。

## 8. 静态导出（F3）

`render_dashboard` 增加一次替换：`__AUTO_REFRESH_INTERVAL__` → `"0"`。
静态 HTML 无 API 可达，不产生轮询请求；其余行为不变。

## 9. 测试策略（验收 4、5）

新增 `tests/test_auto_refresh.py`：

1. `auto_refresh_settings`：缺省 (True,60)；自定义值；`enabled:false`；非法类型回落 60；小于 10 钳制；
2. `AutoCollector`：注入假 collect_func、间隔 0.05s → 立即执行一次且 0.2s 内 ≥2 次；collect_func 抛异常后下轮仍执行；`stop()` 后计数不再增长、线程结束；
3. 端到端：真实 build_server（127.0.0.1:0）+ AutoCollector，collect_func 直接向 sqlite 写入一条结构数据 → httpx 轮询 `/api/reports` 能读到变化；结束 shutdown/stop。

扩展：

- test_export：静态输出含 `AUTO_REFRESH_INTERVAL = 0`、无占位符；
- test_server：GET `/` 输出含正整数间隔。

## 10. 不变量与回归边界

- 迭代一、迭代二全部 95 个测试必须继续通过；
- 不新增第三方依赖、不新增写接口、自动采集零推送；
- SQLite 沿用"每操作独立连接"模式，无线程共享连接；
- 手动命令（`--run/--view/--check`）输出与退出码不变。
