# 智能日报生成器 · 迭代二：任务拆解（tasks-v2）

> 增量任务清单，共 7 个任务。依赖 DAG：
>
> ```text
> T1 ─┬─→ T3 ─→ T4 ─→ T5 ─→ T7
> T2 ─┘               └─→ T6 ─→ T7
> ```
>
> 关键路径：T2 → T3 → T4 → T5 → T7；T5 与 T6 在 T4 后可并行。

| # | 任务 | 产物 | 依赖 | 验收 |
|---|---|---|---|---|
| T1 | DailyReport 增加 failed_sources，管道全程传递 | shared/models.py、main.py | — | 全量回归不破坏 77 测试 |
| T2 | 日报 → 看板 JSON 序列化器 | shared/serializer.py + tests | — | 快照测试：字段名、空 GitHub→null、HH:MM |
| T3 | SQLite data_json 列迁移与读写 | shared/storage.py + tests | T1, T2 | 旧库升级幂等；旧行 data_json 为空；新行 round-trip |
| T4 | Open Design 原型改造为 webapp/dashboard.html（占位符 + 动态启动） | webapp 模板 | T3 | 静态注入与 null+fetch 两种模式逻辑自洽 |
| T5 | 静态导出 + `--view` 升级 | webapp/export.py、main.py + tests | T4 | 单文件可开；指定日期默认选中；无数据提示 |
| T6 | 只读本地 HTTP 服务 + `--serve` | webapp/server.py、main.py + tests | T4 | `/` 与 `/api/reports`、404/405；仅 127.0.0.1；Ctrl+C 退出 0 |
| T7 | 全量回归 + `--view`/`--serve` 冒烟 | 测试输出 | T5, T6 | 全部测试通过；两入口真实可用 |

## 估算与风险

- 全部使用标准库与现有依赖，不新增第三方包；
- 风险点：`ALTER TABLE` 迁移须在真实旧库文件上验证（已纳入 T3 测试）；模板改造保持视觉零改动，仅替换数据入口；
- 一期 9/25 历史行无 `data_json`，看板不展示，属 proposal-v2 §3 已确认的排除项。
