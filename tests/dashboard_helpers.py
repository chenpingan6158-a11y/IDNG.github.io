"""二期测试共用：构建含成员明细的 DailyReport。"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.models import (
    CommitRecord,
    DailyReport,
    MemberReport,
    MessageRecord,
    TaskRecord,
)

_UTC = timezone.utc


def sample_report(day: str = "2026-09-26") -> DailyReport:
    """一份两成员、三源齐全的日报（时间均为 UTC 感知）。"""

    report_date = datetime.strptime(day, "%Y-%m-%d").date()

    liu = MemberReport(
        name="刘政剑",
        github_username="chenpingan6158-a11y",
        commits=[
            CommitRecord(
                author="chenpingan6158-a11y",
                message="新增日报采集模块",
                timestamp=datetime(2026, 9, 26, 2, 24, tzinfo=_UTC),
                repo="usermanagersystem.github.io",
                additions=214,
                deletions=32,
                files_changed=6,
            )
        ],
        tasks=[
            TaskRecord(
                assignee="ou_lzj",
                title="飞书任务采集",
                status_from="进行中",
                status_to="已完成",
                updated_at=datetime(2026, 9, 26, 7, 10, tzinfo=_UTC),
            )
        ],
        messages=[
            MessageRecord(
                sender="ou_lzj",
                content="模板已联调通过",
                timestamp=datetime(2026, 9, 26, 3, 2, tzinfo=_UTC),
                chat_name="SDD测试",
            )
        ],
    )

    chen = MemberReport(
        name="陈平安",
        github_username="",
        commits=[],
        tasks=[],
        messages=[
            MessageRecord(
                sender="ou_cpa",
                content="上线前跑 --check",
                timestamp=datetime(2026, 9, 26, 9, 50, tzinfo=_UTC),
                chat_name="SDD测试",
            )
        ],
    )

    return DailyReport(
        date=report_date,
        team_name="研发一组",
        members=[liu, chen],
        generated_at=datetime(2026, 9, 26, 10, 2, tzinfo=_UTC),
        markdown="# md",
        html="<p>html</p>",
        failed_sources=[],
    )
