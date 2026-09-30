"""notifier/lark_bot.py 单元测试（Mock webhook）。"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from notifier import lark_bot
from shared.models import DailyReport


def _make_report() -> DailyReport:
    return DailyReport(
        date=datetime(2026, 9, 25).date(),
        team_name="研发一组",
        generated_at=datetime(2026, 9, 25, 18, 0),
        markdown="# 研发一组日报\n修复了登录问题",
        html="<h1>日报</h1>",
    )


class FakeResp:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class FakeHTTP:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.posted: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict):
        self.posted.append((url, json))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _kwargs() -> dict:
    return {
        "webhook": "https://open.feishu.cn/hook/x",
    }


def test_send_success() -> None:
    http = FakeHTTP([FakeResp({"code": 0, "msg": "success"})])
    ok = lark_bot.send(_make_report(), "oc_group", http_client=http, **_kwargs())
    assert ok is True
    url, payload = http.posted[0]
    assert url.endswith("/hook/x")
    assert payload["msg_type"] == "interactive"
    markdown = payload["card"]["elements"][0]["text"]["content"]
    assert markdown == "# 研发一组日报\n修复了登录问题"  # Markdown 格式
    title = payload["card"]["header"]["title"]["content"]
    assert "研发一组 日报 2026-09-25" in title


def test_send_retries_then_false_on_rejection() -> None:
    http = FakeHTTP(
        [
            FakeResp({"code": 19001, "msg": "bad"}),
            FakeResp({"code": 19001, "msg": "bad"}),
        ]
    )
    ok = lark_bot.send(_make_report(), "oc_group", http_client=http, **_kwargs())
    assert ok is False
    assert len(http.posted) == 2  # 共尝试 2 次


def test_send_retries_on_network_error() -> None:
    http = FakeHTTP(
        [httpx.ConnectError("boom"), FakeResp({"code": 0})]
    )
    ok = lark_bot.send(_make_report(), "oc_group", http_client=http, **_kwargs())
    assert ok is True


def test_legacy_status_code_zero_is_success() -> None:
    http = FakeHTTP([FakeResp({"StatusCode": 0, "StatusMessage": "ok"})])
    ok = lark_bot.send(_make_report(), "oc_group", http_client=http, **_kwargs())
    assert ok is True
