"""collector/_lark_client.py 单元测试（token 缓存 / 刷新 / 重试）。"""

from __future__ import annotations

import httpx
import pytest

from collector._lark_client import LarkClient
from shared.errors import CollectorError


class FakeResp:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class ScriptedHTTP:
    def __init__(self, scripts: list[object]) -> None:
        self.scripts = list(scripts)
        self.requests: list[tuple[str, str]] = []

    def request(self, method, url, params=None, json=None, headers=None):
        self.requests.append((method, url))
        result = self.scripts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


_TOKEN_OK = {"code": 0, "tenant_access_token": "t-abc", "expire": 7200}


def _client(http: ScriptedHTTP, **kwargs) -> LarkClient:
    return LarkClient("app", "secret", http_client=http, sleeper=lambda _: None, **kwargs)


def test_fetches_and_uses_token() -> None:
    http = ScriptedHTTP(
        [
            FakeResp(_TOKEN_OK),
            FakeResp({"code": 0, "data": {"ok": True}}),
        ]
    )
    client = _client(http)
    data = client.request("GET", "/open-apis/test")
    assert data == {"ok": True}
    assert http.requests[0][1].endswith("/internal")


def test_token_cached_until_expiry() -> None:
    http = ScriptedHTTP(
        [
            FakeResp(_TOKEN_OK),
            FakeResp({"code": 0, "data": {}}),
            FakeResp({"code": 0, "data": {}}),
        ]
    )
    client = _client(http)
    client.request("GET", "/a")
    client.request("GET", "/b")
    token_calls = [u for _, u in http.requests if u.endswith("/internal")]
    assert len(token_calls) == 1


def test_refresh_token_when_invalid() -> None:
    http = ScriptedHTTP(
        [
            FakeResp(_TOKEN_OK),
            FakeResp({"code": 99991663, "msg": "token expired"}),
            FakeResp(_TOKEN_OK),
            FakeResp({"code": 0, "data": {"refreshed": True}}),
        ]
    )
    client = _client(http)
    data = client.request("GET", "/a")
    assert data == {"refreshed": True}
    token_calls = [u for _, u in http.requests if u.endswith("/internal")]
    assert len(token_calls) == 2


def test_network_error_retries_then_succeeds() -> None:
    http = ScriptedHTTP(
        [
            FakeResp(_TOKEN_OK),
            httpx.TimeoutException("timeout"),
            httpx.ConnectError("boom"),
            FakeResp({"code": 0, "data": {"late": True}}),
        ]
    )
    client = _client(http)
    data = client.request("GET", "/a")
    assert data == {"late": True}


def test_persistent_error_raises() -> None:
    http = ScriptedHTTP(
        [
            FakeResp(_TOKEN_OK),
            FakeResp({"code": 99999, "msg": "boom"}),
            FakeResp({"code": 99999, "msg": "boom"}),
            FakeResp({"code": 99999, "msg": "boom"}),
        ]
    )
    client = _client(http)
    with pytest.raises(CollectorError, match="最终失败"):
        client.request("GET", "/a")


def test_paginate_walks_pages() -> None:
    page_one = {
        "code": 0,
        "data": {"items": [{"id": 1}], "has_more": True, "page_token": "tok2"},
    }
    page_two = {"code": 0, "data": {"items": [{"id": 2}], "has_more": False}}
    http = ScriptedHTTP([FakeResp(_TOKEN_OK), FakeResp(page_one), FakeResp(page_two)])
    client = _client(http)

    items = list(client.paginate("/open-apis/list"))
    assert [item["id"] for item in items] == [1, 2]
