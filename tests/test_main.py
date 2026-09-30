"""main.py 单元测试：工作日识别、健康检查与管道编排。"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest

import main
from shared.config import load_config
from shared.errors import CollectorError, ConfigurationError
from shared.models import CommitRecord, TaskRecord
from shared.storage import ReportStorage

_CONFIG_YAML_TEMPLATE = """
team:
  name: "测试团队"
members:
  - name: "张三"
    github: "zhangsan"
    lark: "ou_zhangsan"
github:
  enabled: true
  base_url: "https://api.github.com"
  token_env: "GITHUB_TOKEN"
  repos: ["org/repo"]
  per_page: 30
  timeout: 5
lark_task:
  enabled: true
  app_id_env: "LARK_APP_ID"
  app_secret_env: "LARK_APP_SECRET"
  project_id: "proj_x"
  timeout: 5
lark_message:
  enabled: true
  app_id_env: "LARK_APP_ID"
  app_secret_env: "LARK_APP_SECRET"
  chat_id: "oc_x"
  keywords: ["上线"]
  sensitive_words: ["薪资"]
  chat_name: "研发群"
  timeout: 5
email:
  enabled: true
  smtp_host: "smtp.company.com"
  smtp_port: 465
  use_ssl: true
  username_env: "SMTP_USERNAME"
  password_env: "SMTP_PASSWORD"
  sender: "report@company.com"
  recipients: ["leader@company.com"]
lark_bot:
  enabled: true
  webhook: "https://open.feishu.cn/hook/x"
  chat_id: "oc_x"
  timeout: 5
storage:
  sqlite_path: "{db_path}"
schedule:
  holidays: []
  workdays: []
"""


@pytest.fixture()
def config(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    db_path = str(tmp_path / "reports.db").replace("\\", "/")
    yaml_path.write_text(
        _CONFIG_YAML_TEMPLATE.format(db_path=db_path),
        encoding="utf-8",
    )
    return load_config(yaml_path)


# ---- 工作日识别 ----

def test_is_workday_weekday(config) -> None:
    # 2026-09-28 是周一
    assert main.is_workday(date(2026, 9, 28), config) is True


def test_is_workday_weekend(config) -> None:
    # 2026-09-26 是周六
    assert main.is_workday(date(2026, 9, 26), config) is False


def test_config_workday_override(config, monkeypatch) -> None:
    monkeypatch.setitem(config._data["schedule"], "workdays", ["2026-09-26"])
    assert main.is_workday(date(2026, 9, 26), config) is True


def test_config_holiday_override(config, monkeypatch) -> None:
    monkeypatch.setitem(config._data["schedule"], "holidays", ["2026-09-28"])
    assert main.is_workday(date(2026, 9, 28), config) is False


# ---- 健康检查 ----

def test_run_check_all_pass(config, monkeypatch) -> None:
    monkeypatch.setattr(main, "_check_github", lambda cfg: None)
    monkeypatch.setattr(main, "_check_lark", lambda cfg, section: None)
    monkeypatch.setattr(main, "_check_smtp", lambda cfg: None)
    assert main.run_check(config) is True


def test_run_check_one_failure(config, monkeypatch) -> None:
    def boom(cfg) -> None:
        raise ConfigurationError("nope", source="check")

    monkeypatch.setattr(main, "_check_github", boom)
    monkeypatch.setattr(main, "_check_lark", lambda cfg, section: None)
    monkeypatch.setattr(main, "_check_smtp", lambda cfg: None)
    assert main.run_check(config) is False


# ---- 日报页面查看 ----

def test_view_report_opens_html_file(config) -> None:
    from generator.formatter import generate

    report = generate([], date(2026, 9, 28), "测试团队")
    with ReportStorage(config["storage"]["sqlite_path"]) as storage:
        storage.save_report(report)

    opened: list[str] = []
    assert main.view_report(config, "2026-09-28", opener=opened.append) is True

    assert len(opened) == 1
    assert opened[0].startswith("file:") and opened[0].endswith(".html")

    from pathlib import Path

    html_file = Path(config["storage"]["sqlite_path"]).parent / "report-2026-09-28.html"
    assert html_file.exists()
    assert "工作日报" in html_file.read_text(encoding="utf-8")


def test_view_report_missing_date_returns_false(config) -> None:
    def must_not_open(uri: str) -> None:
        raise AssertionError("无日报时不应打开页面")

    assert main.view_report(config, "2026-09-26", opener=must_not_open) is False


# ---- 默认动作：启动看板 ----

def test_default_invocation_starts_dashboard(config, monkeypatch) -> None:
    called: list[str] = []

    import webapp.server

    monkeypatch.setattr(
        webapp.server, "serve", lambda cfg: called.append("serve")
    )

    assert main.main(["--config", config.source_path]) == 0
    assert called == ["serve"]


def test_explicit_serve_starts_dashboard(config, monkeypatch) -> None:
    called: list[str] = []

    import webapp.server

    monkeypatch.setattr(
        webapp.server, "serve", lambda cfg: called.append("serve")
    )

    assert main.main(["--config", config.source_path, "--serve"]) == 0
    assert called == ["serve"]


# ---- 管道 ----
_MONDAY = datetime(2026, 9, 28, 17, 0, tzinfo=timezone(timedelta(hours=8)))


def _patch_collectors(monkeypatch, *, fail: set[str] | None = None) -> dict:
    fail = fail or set()
    counts = {"commits": 0, "tasks": 0, "messages": 0}

    def fake_github(repos, since, until, **kwargs):
        if "github" in fail:
            raise CollectorError("github down", source="github")
        counts["commits"] += 1
        return [
            CommitRecord(
                author="zhangsan",
                message="feat",
                timestamp=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
                repo="org/repo",
                additions=1,
                deletions=0,
                files_changed=1,
            )
        ]

    def fake_lark_task(project_id, since, until, **kwargs):
        if "lark_task" in fail:
            raise CollectorError("task down", source="lark_task")
        counts["tasks"] += 1
        return [
            TaskRecord(
                assignee="ou_zhangsan",
                title="完成开发任务",
                status_from="进行中",
                status_to="已完成",
                updated_at=datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc),
            )
        ]

    def fake_lark_msg(chat_id, keywords, since, until, **kwargs):
        if "lark_message" in fail:
            raise CollectorError("msg down", source="lark_message")
        counts["messages"] += 1
        return []

    monkeypatch.setattr(main.github, "collect", fake_github)
    monkeypatch.setattr(main.lark_task, "collect", fake_lark_task)
    monkeypatch.setattr(main.lark_msg, "collect", fake_lark_msg)
    return counts


def test_pipeline_non_workday_is_skipped(config) -> None:
    saturday = datetime(2026, 9, 26, 17, 0, tzinfo=timezone(timedelta(hours=8)))
    assert main.run_pipeline(config, now=saturday) is True


def test_pipeline_full_run_pushes_and_persists(config, monkeypatch) -> None:
    _patch_collectors(monkeypatch)
    pushed: list[str] = []
    monkeypatch.setattr(
        main.email, "send", lambda report, recipients, **kw: pushed.append("email") or True
    )
    monkeypatch.setattr(
        main.lark_bot, "send", lambda report, chat_id, **kw: pushed.append("lark") or True
    )

    ok = main.run_pipeline(config, now=_MONDAY)
    assert ok is True
    assert pushed == ["email", "lark"]

    with ReportStorage(config["storage"]["sqlite_path"]) as storage:
        row = storage.get_report("2026-09-28", "测试团队")
    assert row is not None
    assert "### 代码提交" in row["markdown"]


def test_pipeline_dry_run_does_not_push(config, monkeypatch) -> None:
    _patch_collectors(monkeypatch)

    def should_not_call(*args, **kwargs):
        raise AssertionError("push must not happen in dry-run")

    monkeypatch.setattr(main.email, "send", should_not_call)
    monkeypatch.setattr(main.lark_bot, "send", should_not_call)

    assert main.run_pipeline(config, now=_MONDAY, dry_run=True) is True


def test_pipeline_single_source_failure_marks_report(config, monkeypatch) -> None:
    _patch_collectors(monkeypatch, fail={"github"})
    monkeypatch.setattr(main.email, "send", lambda *a, **kw: True)
    monkeypatch.setattr(main.lark_bot, "send", lambda *a, **kw: True)

    ok = main.run_pipeline(config, now=_MONDAY)
    assert ok is True

    with ReportStorage(config["storage"]["sqlite_path"]) as storage:
        row = storage.get_report("2026-09-28", "测试团队")
    assert row is not None
    assert "数据获取失败" in row["markdown"]


def test_pipeline_all_sources_fail_returns_false(config, monkeypatch) -> None:
    _patch_collectors(
        monkeypatch, fail={"github", "lark_task", "lark_message"}
    )

    def should_not_call(*args, **kwargs):
        raise AssertionError("no push when all sources fail")

    monkeypatch.setattr(main.email, "send", should_not_call)
    monkeypatch.setattr(main.lark_bot, "send", should_not_call)

    assert main.run_pipeline(config, now=_MONDAY) is False
