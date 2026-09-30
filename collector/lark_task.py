"""飞书任务采集模块（design.md §2、§4.1）。

通过 Task v2 接口列出项目内的任务，识别采集窗口内发生的状态变更：
- created_at 落在窗口内：(无) → 新建
- completed_at 落在窗口内：进行中 → 已完成
飞书 token 失效时由 LarkClient 自动刷新并重试。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from collector._lark_client import LARK_BASE_URL, LarkClient
from shared.models import TaskRecord

_TASKLIST_TASKS_PATH = "/open-apis/task/v2/tasklists/{guid}/tasks"


def _to_milliseconds(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def _from_milliseconds(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _pick_assignee(task: dict) -> str:
    members = task.get("members", [])
    for member in members:
        if member.get("role") == "assignee":
            return member.get("id", "")
    return members[0].get("id", "") if members else ""


def _detect_change(
    task: dict,
    since_ms: int,
    until_ms: int,
) -> tuple[str, str, int] | None:
    """返回 (status_from, status_to, event_time_ms)，无变更返回 None。"""

    created_at = int(task.get("created_at") or 0)
    completed_at = int(task.get("completed_at") or 0)

    if since_ms <= created_at <= until_ms:
        return "(无)", "新建", created_at
    if since_ms <= completed_at <= until_ms:
        return "进行中", "已完成", completed_at
    return None


def collect(
    project_id: str,
    since: datetime,
    until: datetime,
    *,
    app_id_env: str = "LARK_APP_ID",
    app_secret_env: str = "LARK_APP_SECRET",
    base_url: str = LARK_BASE_URL,
    timeout: float = 10.0,
    lark_client: LarkClient | None = None,
) -> list[TaskRecord]:
    """获取指定项目中在 [since, until] 内发生状态变更的任务记录。"""

    client = lark_client or LarkClient(
        os.environ.get(app_id_env, ""),
        os.environ.get(app_secret_env, ""),
        base_url=base_url,
        timeout=timeout,
    )

    since_ms = _to_milliseconds(since)
    until_ms = _to_milliseconds(until)

    records: list[TaskRecord] = []
    for slim in client.paginate(
        _TASKLIST_TASKS_PATH.format(guid=project_id),
        {"page_size": 50, "user_id_type": "open_id"},
    ):
        # 清单列表接口返回精简字段（无 created_at），须按 guid 取任务详情
        detail = client.request(
            "GET",
            f"/open-apis/task/v2/tasks/{slim['guid']}",
            params={"user_id_type": "open_id"},
        )
        task = detail.get("task", slim)
        change = _detect_change(task, since_ms, until_ms)
        if change is None:
            continue
        status_from, status_to, event_time_ms = change
        records.append(
            TaskRecord(
                assignee=_pick_assignee(task),
                title=task.get("summary", ""),
                status_from=status_from,
                status_to=status_to,
                updated_at=_from_milliseconds(event_time_ms),
            )
        )

    return records
