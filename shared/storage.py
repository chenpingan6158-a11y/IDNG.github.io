"""SQLite 日报历史存储（ADR-002，design.md §2 shared/storage.py）。

每天仅由定时任务写入一次，无并发写入场景，故使用标准库 sqlite3 即可。
同一 (日期, 团队) 重复写入时执行 upsert。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from shared.models import DailyReport
from shared.serializer import report_to_dict

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    team_name    TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    markdown     TEXT NOT NULL,
    html         TEXT NOT NULL,
    UNIQUE (date, team_name)
);
"""


class ReportStorage:
    """日报历史的 SQLite 存取。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._migrate_data_json()
        self._conn.commit()

    def _migrate_data_json(self) -> None:
        """对一期库幂等添加 data_json 列（design-v2 §4）。"""

        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(reports)")
        }
        if "data_json" not in columns:
            self._conn.execute(
                "ALTER TABLE reports ADD COLUMN data_json TEXT NOT NULL DEFAULT ''"
            )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "ReportStorage":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def save_report(self, report: DailyReport) -> None:
        """写入或更新一条日报记录。"""

        generated_at = report.generated_at or datetime.now()
        data_json = json.dumps(
            report_to_dict(report), ensure_ascii=False
        )
        self._conn.execute(
            """
            INSERT INTO reports
                (date, team_name, generated_at, markdown, html, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, team_name) DO UPDATE SET
                generated_at = excluded.generated_at,
                markdown     = excluded.markdown,
                html         = excluded.html,
                data_json    = excluded.data_json
            """,
            (
                report.date.isoformat(),
                report.team_name,
                generated_at.isoformat(),
                report.markdown,
                report.html,
                data_json,
            ),
        )
        self._conn.commit()

    def get_report(self, date_iso: str, team_name: str) -> dict | None:
        """按日期与团队名查询日报。"""

        row = self._conn.execute(
            "SELECT * FROM reports WHERE date = ? AND team_name = ?",
            (date_iso, team_name),
        ).fetchone()
        return dict(row) if row else None

    def list_reports(self, limit: int = 30) -> list[dict]:
        """按日期倒序列出日报历史。"""

        rows = self._conn.execute(
            "SELECT id, date, team_name, generated_at FROM reports "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def iter_report_data(self, limit: int = 30) -> list[dict]:
        """返回具备结构化数据的日报字典列表（看板历史来源，design-v2 §4）。"""

        rows = self._conn.execute(
            "SELECT data_json FROM reports WHERE data_json <> '' "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [json.loads(row["data_json"]) for row in rows]
