# 智能日报生成器 · 迭代三任务清单（tasks-v3）

> 依据：proposal-v3 / design-v3
> DAG：T1 → T2 → T4 → T5 → T6；T3 与 T2 并行（T4 依赖 T1、T2、T3）

| 编号 | 任务 | 产出 | 依赖 |
|---|---|---|---|
| T1 | `run_pipeline` 增加 `force` 参数（跳过工作日判断，默认 False） | `main.py` | — |
| T2 | `auto_refresh_settings()` 配置解析 + `AutoCollector` 调度器（立即执行、周期循环、异常容错、Event 可停） | `webapp/server.py` | T1 |
| T3 | 前端：`__AUTO_REFRESH_INTERVAL__` 占位符、`startPolling()` 轮询、指纹比对、视图状态保留 | `webapp/dashboard.html` | — |
| T4 | 接线：`render_served_page(interval)`、`build_server` 记录间隔、`serve` 启停采集线程；`export.py` 静态替换为 0 | `webapp/server.py`、`webapp/export.py` | T1、T2、T3 |
| T5 | 测试：新增 `test_auto_refresh.py`（settings 用例、Collector 调度/容错/停止、端到端轮询），扩展 test_export / test_server | `tests/` | T4 |
| T6 | 全量回归（现有 95 测试不破坏）+ 真实冒烟：重启服务后发消息，等待 ≤2 分钟确认页面自动上屏 | 验证记录 | T5 |

## 完成定义

- T1~T5 代码与测试齐备，`pytest tests/ -q` 全绿；
- T6 真实环境验证"发消息后自动出现，零人工操作"；
- 不引入第三方依赖、不触发自动推送、不改动既有手动命令语义。
