"""storage data_json 迁移与读写测试（design-v2 §4）。"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dashboard_helpers import sample_report
from shared.storage import ReportStorage

_OLD_SCHEMA = """
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    team_name TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    markdown TEXT NOT NULL,
    html TEXT NOT NULL,
    UNIQUE (date, team_name)
);
"""


def _build_legacy_db(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(_OLD_SCHEMA)
    conn.execute(
        "INSERT INTO reports (date, team_name, generated_at, markdown, html) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            "2026-09-25",
            "研发一组",
            datetime(2026, 9, 25, 18, 0).isoformat(),
            "# 一期日报",
            "<p>一期</p>",
        ),
    )
    conn.commit()
    conn.close()


def test_migrates_legacy_database_idempotently(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    _build_legacy_db(db_path)

    storage = ReportStorage(db_path)

    columns = {
        row["name"]
        for row in storage._conn.execute("PRAGMA table_info(reports)")
    }
    assert "data_json" in columns

    # 再次构造不应报错（幂等）
    storage.close()
    ReportStorage(db_path).close()


def test_legacy_rows_keep_empty_data_json(tmp_path) -> None:
    db_path = tmp_path / "reports.db"
    _build_legacy_db(db_path)

    storage = ReportStorage(db_path)
    row = storage.get_report("2026-09-25", "研发一组")
    assert row is not None
    assert row["data_json"] == ""
    assert row["markdown"] == "# 一期日报"
    assert storage.iter_report_data() == []
    storage.close()


def test_new_report_data_roundtrip(tmp_path) -> None:
    storage = ReportStorage(tmp_path / "reports.db")
    storage.save_report(sample_report())

    data = storage.iter_report_data()
    assert len(data) == 1
    report = data[0]
    assert report["date"] == "2026-09-26"
    assert report["members"][0]["commits"][0]["message"] == "新增日报采集模块"

    # upsert 后仍为一条且 data_json 同步更新
    storage.save_report(sample_report())
    assert len(storage.iter_report_data()) == 1
    storage.close()
