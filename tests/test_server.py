"""webapp/server.py 只读 HTTP 服务测试（design-v2 §7）。"""

from __future__ import annotations

import threading

import httpx
import pytest

from dashboard_helpers import sample_report
from shared.storage import ReportStorage
from webapp.server import build_server


@pytest.fixture
def running_server(tmp_path):
    db_path = tmp_path / "reports.db"
    with ReportStorage(db_path) as storage:
        storage.save_report(sample_report())

    config = {"storage": {"sqlite_path": str(db_path)}}
    server = build_server(config, host="127.0.0.1", port=0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield f"http://{host}:{port}", server

    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_server_is_bound_to_loopback(running_server) -> None:
    _, server = running_server
    assert server.server_address[0] == "127.0.0.1"


def test_index_serves_dynamic_dashboard(running_server) -> None:
    base, _ = running_server
    resp = httpx.get(base + "/", timeout=10)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "var REPORTS = null" in resp.text
    assert "var AUTO_REFRESH_INTERVAL = 60" in resp.text
    assert 'fetch("api/reports")' in resp.text


def test_api_reports_returns_real_data(running_server) -> None:
    base, _ = running_server
    resp = httpx.get(base + "/api/reports", timeout=10)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 0
    assert len(payload["reports"]) == 1
    assert payload["reports"][0]["date"] == "2026-09-26"


def test_api_reports_date_filter(running_server) -> None:
    base, _ = running_server

    hit = httpx.get(base + "/api/reports", params={"date": "2026-09-26"}, timeout=10)
    assert len(hit.json()["reports"]) == 1

    miss = httpx.get(base + "/api/reports", params={"date": "2026-01-01"}, timeout=10)
    assert miss.json()["reports"] == []


def test_unknown_path_returns_404(running_server) -> None:
    base, _ = running_server
    resp = httpx.get(base + "/nope", timeout=10)

    assert resp.status_code == 404
    assert resp.json()["code"] == 404


def test_non_get_methods_are_rejected(running_server) -> None:
    base, _ = running_server
    for method in ("post", "put", "delete", "patch"):
        resp = getattr(httpx, method)(base + "/api/reports", timeout=10)
        assert resp.status_code == 405
