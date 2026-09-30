"""看板静态导出（design-v2 §6）：占位符替换，产出自包含 HTML。"""

from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).with_name("dashboard.html")
_REPORTS_PLACEHOLDER = "__REPORTS_JSON__"
_INITIAL_DATE_PLACEHOLDER = "__INITIAL_DATE__"
_AUTO_REFRESH_PLACEHOLDER = "__AUTO_REFRESH_INTERVAL__"


def _safe_json_text(reports: list[dict]) -> str:
    text = json.dumps(reports, ensure_ascii=False)
    # 防止数据内容中出现 "</script>" 截断页面脚本
    return text.replace("</", "<\\/")


def render_dashboard(
    reports: list[dict], initial_date: str | None = None
) -> str:
    """将报告数据注入看板模板，返回完整 HTML 字符串。"""

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template.replace(_REPORTS_PLACEHOLDER, _safe_json_text(reports))
        .replace(_INITIAL_DATE_PLACEHOLDER, json.dumps(initial_date, ensure_ascii=False))
        .replace(_AUTO_REFRESH_PLACEHOLDER, "0")
    )


def export_dashboard(
    reports: list[dict],
    out_path: str | Path,
    initial_date: str | None = None,
) -> Path:
    """渲染并写入文件，返回输出路径。"""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_dashboard(reports, initial_date), encoding="utf-8"
    )
    return out_path
