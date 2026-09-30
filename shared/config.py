"""配置读取与校验（design.md §2 shared/config.py）。

- 从 YAML 文件加载配置；
- 缺失必填字段时抛出 ConfigurationError；
- 提供属性式访问与成员身份映射的便捷方法。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from shared.errors import ConfigurationError

# 各 section 的必填字段（点号表示嵌套路径）
_REQUIRED: dict[str, list[str]] = {
    "team": ["name"],
    "members": [],
    "github": ["base_url", "repos"],
    "lark_task": ["project_id"],
    "lark_message": ["chat_id", "keywords"],
    "email": ["smtp_host", "smtp_port", "sender", "recipients"],
    "lark_bot": ["webhook"],
    "storage": ["sqlite_path"],
}


class Config(Mapping):
    """只读配置对象，支持 config['team']['name'] 与 config.get_path(...)。"""

    def __init__(self, data: Mapping[str, Any], source_path: str | Path = "") -> None:
        self._data = dict(data)
        self.source_path = str(source_path)

    # Mapping 接口
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get_path(self, path: str, default: Any = None) -> Any:
        """按 'a.b.c' 路径取值。"""
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node

    # 业务便捷方法
    @property
    def team_name(self) -> str:
        return self._data["team"]["name"]

    @property
    def members(self) -> list[dict[str, str]]:
        return list(self._data.get("members", []))

    def enabled_sources(self) -> list[str]:
        """返回已启用的数据源名称。"""
        return [
            name
            for name in ("github", "lark_task", "lark_message")
            if self._data.get(name, {}).get("enabled", False)
        ]

    def enabled_channels(self) -> list[str]:
        """返回已启用的推送渠道名称。"""
        return [
            name
            for name in ("email", "lark_bot")
            if self._data.get(name, {}).get("enabled", False)
        ]


def load_config(path: str | Path = "config.yaml") -> Config:
    """加载并校验配置文件。"""

    file_path = Path(path)
    if not file_path.exists():
        raise ConfigurationError(
            f"配置文件不存在：{file_path}", source="config"
        )

    try:
        raw = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML 解析失败：{exc}", source="config") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("配置文件顶层必须是键值映射", source="config")

    config = Config(raw, source_path=file_path)
    _validate(config)
    return config


def _validate(config: Config) -> None:
    """检查必填字段与基本一致性。"""

    for section, fields in _REQUIRED.items():
        if section not in config:
            raise ConfigurationError(f"缺少配置节：{section}", source="config")
        for field_path in fields:
            full_path = f"{section}.{field_path}"
            if config.get_path(full_path) in (None, "", []):
                raise ConfigurationError(f"缺少必填配置项：{full_path}", source="config")

    members = config.members
    if not members:
        raise ConfigurationError("members 至少需要配置一名成员", source="config")

    seen_github: set[str] = set()
    for index, member in enumerate(members):
        # github 可留空（仅有飞书身份的成员）；name / lark 必填
        for key in ("name", "lark"):
            if not member.get(key):
                raise ConfigurationError(
                    f"members[{index}] 缺少字段：{key}", source="config"
                )
        github_name = member.get("github")
        if github_name:
            if github_name in seen_github:
                raise ConfigurationError(
                    f"members 中 GitHub 用户名重复：{github_name}", source="config"
                )
            seen_github.add(github_name)

    if not config.enabled_sources():
        raise ConfigurationError(
            "至少需要启用一个数据源（github / lark_task / lark_message）",
            source="config",
        )
