"""webapp/export.py 静态导出测试（design-v2 §6）。"""

from __future__ import annotations

import json
import re

from dashboard_helpers import sample_report
from shared.serializer import report_to_dict
from webapp.export import export_dashboard, render_dashboard


def test_render_dashboard_replaces_placeholders() -> None:
    reports = [report_to_dict(sample_report())]
    html = render_dashboard(reports, initial_date="2026-09-26")

    assert "__REPORTS_JSON__" not in html
    assert "__INITIAL_DATE__" not in html
    assert "__AUTO_REFRESH_INTERVAL__" not in html
    assert "var REPORTS = " in html
    assert "var AUTO_REFRESH_INTERVAL = 0" in html  # 静态文件不轮询
    assert '"2026-09-26"' in html
    assert "新增日报采集模块" in html


def test_render_without_initial_date_uses_null() -> None:
    reports = [report_to_dict(sample_report())]
    html = render_dashboard(reports)

    assert re.search(r"date:\s*null,", html)


def test_script_closing_tag_in_data_is_escaped() -> None:
    report = sample_report()
    report.members[0].commits[0].message = "evil </script><script>alert(1)</script>"
    reports = [report_to_dict(report)]
    html = render_dashboard(reports)

    # 注入 JSON 中的 </ 被转义，页面自身脚本闭合标签数量不变
    assert "</script>" not in html.split("var REPORTS = ", 1)[1].split(";\n", 1)[0]
    assert "<\\/script>" in html


def test_export_dashboard_writes_file(tmp_path) -> None:
    reports = [report_to_dict(sample_report())]
    out = export_dashboard(reports, tmp_path / "nested" / "dashboard.html")

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert content.startswith("<!DOCTYPE html>")
    assert "研发一组" in content
