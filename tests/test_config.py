"""shared/config.py 单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import Config, load_config
from shared.errors import ConfigurationError

VALID_CONFIG = """
team:
  name: "测试团队"
members:
  - name: "张三"
    github: "zhangsan"
    lark: "zhangsan@company.com"
github:
  enabled: true
  base_url: "https://api.github.com"
  token_env: "GITHUB_TOKEN"
  repos: ["org/repo"]
  per_page: 30
lark_task:
  enabled: true
  app_id_env: "LARK_APP_ID"
  app_secret_env: "LARK_APP_SECRET"
  project_id: "proj_x"
lark_message:
  enabled: false
  app_id_env: "LARK_APP_ID"
  app_secret_env: "LARK_APP_SECRET"
  chat_id: "oc_x"
  keywords: ["上线"]
  sensitive_words: ["薪资"]
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
  enabled: false
  webhook: "https://open.feishu.cn/hook/x"
storage:
  sqlite_path: "data/test.db"
schedule:
  holidays: []
  workdays: []
"""


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_valid_config(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    assert isinstance(config, Config)
    assert config.team_name == "测试团队"
    assert len(config.members) == 1
    assert config.enabled_sources() == ["github", "lark_task"]
    assert config.enabled_channels() == ["email"]


def test_get_path(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, VALID_CONFIG))
    assert config.get_path("team.name") == "测试团队"
    assert config.get_path("not.exist", "default") == "default"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="配置文件不存在"):
        load_config(tmp_path / "nope.yaml")


def test_missing_required_section_raises(tmp_path: Path) -> None:
    broken = VALID_CONFIG.replace('storage:\n  sqlite_path: "data/test.db"\n', "")
    with pytest.raises(ConfigurationError, match="缺少配置节"):
        load_config(_write(tmp_path, broken))


def test_missing_required_field_raises(tmp_path: Path) -> None:
    broken = VALID_CONFIG.replace('project_id: "proj_x"\n', "")
    with pytest.raises(ConfigurationError, match="缺少必填配置项"):
        load_config(_write(tmp_path, broken))


def test_empty_members_raises(tmp_path: Path) -> None:
    broken = VALID_CONFIG.replace(
        'members:\n  - name: "张三"\n    github: "zhangsan"\n    lark: "zhangsan@company.com"\n',
        "members: []\n",
    )
    with pytest.raises(ConfigurationError, match="至少需要配置一名成员"):
        load_config(_write(tmp_path, broken))


def test_no_enabled_source_raises(tmp_path: Path) -> None:
    broken = VALID_CONFIG.replace("enabled: true", "enabled: false")
    with pytest.raises(ConfigurationError, match="至少需要启用一个数据源"):
        load_config(_write(tmp_path, broken))


def test_duplicate_github_username_raises(tmp_path: Path) -> None:
    extra = '  - name: "另一个"\n    github: "zhangsan"\n    lark: "other@company.com"\n'
    broken = VALID_CONFIG.replace(
        '    lark: "zhangsan@company.com"\n',
        '    lark: "zhangsan@company.com"\n' + extra,
    )
    with pytest.raises(ConfigurationError, match="GitHub 用户名重复"):
        load_config(_write(tmp_path, broken))
