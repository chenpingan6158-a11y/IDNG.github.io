"""shared/envfile.py 单元测试。"""

from __future__ import annotations

import pytest

from shared.envfile import load_envfile

_CONTENT = """
# 这是注释
export LARK_APP_ID=cli_xxx
LARK_APP_SECRET="sec-1234"
SIMPLE='plain value # not comment'

EMPTY=
"""


def test_load_envfile_parses_and_sets_environ(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text(_CONTENT, encoding="utf-8")
    for key in ("LARK_APP_ID", "LARK_APP_SECRET", "SIMPLE", "EMPTY"):
        monkeypatch.delenv(key, raising=False)

    loaded = load_envfile(env)

    assert loaded == {
        "LARK_APP_ID": "cli_xxx",
        "LARK_APP_SECRET": "sec-1234",
        "SIMPLE": "plain value # not comment",
        "EMPTY": "",
    }
    import os

    assert os.environ["LARK_APP_ID"] == "cli_xxx"


def test_existing_environment_is_not_overridden(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("LARK_APP_ID=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LARK_APP_ID", "from-process")

    loaded = load_envfile(env)

    assert loaded == {}
    import os

    assert os.environ["LARK_APP_ID"] == "from-process"


def test_override_mode_replaces_existing(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("LARK_APP_ID=from-file\n", encoding="utf-8")
    monkeypatch.setenv("LARK_APP_ID", "from-process")

    loaded = load_envfile(env, override=True)

    assert loaded["LARK_APP_ID"] == "from-file"


def test_missing_file_returns_empty(tmp_path) -> None:
    assert load_envfile(tmp_path / "nope.env") == {}


def test_malformed_lines_ignored(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("=nokey\nNO_EQUAL_SIGN\nGOOD=ok\n", encoding="utf-8")
    monkeypatch.delenv("GOOD", raising=False)

    assert load_envfile(env) == {"GOOD": "ok"}
