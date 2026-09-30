"""shared/storage.py 单元测试。"""

from __future__ import annotations

from datetime import datetime

from shared.models import DailyReport
from shared.storage import ReportStorage


def _make_report(day: str = "2026-09-25") -> DailyReport:
    return DailyReport(
        date=datetime.strptime(day, "%Y-%m-%d").date(),
        team_name="测试团队",
        generated_at=datetime(2026, 9, 25, 18, 0, 0),
        markdown="# 日报",
        html="<h1>日报</h1>",
    )


def test_save_and_get_report(tmp_path) -> None:
    storage = ReportStorage(tmp_path / "reports.db")
    storage.save_report(_make_report())

    row = storage.get_report("2026-09-25", "测试团队")
    assert row is not None
    assert row["markdown"] == "# 日报"
    assert row["html"] == "<h1>日报</h1>"
    storage.close()


def test_upsert_same_day(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    storage = ReportStorage(db_path)

    report = _make_report()
    storage.save_report(report)

    report.markdown = "# 更新后的日报"
    storage.save_report(report)

    rows = storage.list_reports()
    assert len(rows) == 1
    row = storage.get_report("2026-09-25", "测试团队")
    assert row is not None and row["markdown"] == "# 更新后的日报"
    storage.close()


def test_get_missing_report_returns_none(tmp_path) -> None:
    storage = ReportStorage(tmp_path / "reports.db")
    assert storage.get_report("2026-01-01", "不存在") is None
    storage.close()


def test_context_manager(tmp_path) -> None:
    with ReportStorage(tmp_path / "reports.db") as storage:
        storage.save_report(_make_report())
        assert len(storage.list_reports()) == 1
