"""轻量 .env 文件加载（无第三方依赖）。

每行格式：KEY=VALUE，支持：
- 空行与以 '#' 开头的注释；
- 可选的 'export ' 前缀；
- 值两侧成对的单/双引号（引号去除，引号内内容原样保留）。

默认不覆盖进程中已存在的环境变量（显式设置的环境变量优先级更高）。
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export ") :].strip()

    key, sep, value = line.partition("=")
    if not sep:
        return None
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_envfile(path: str | Path, *, override: bool = False) -> dict[str, str]:
    """读取 .env 并写入 os.environ；返回本次实际写入的键值对。

    文件不存在时静默返回空字典（.env 为可选项）。
    """

    path = Path(path)
    if not path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(raw)
        if parsed is None:
            continue
        key, value = parsed
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded
