"""自定义异常与错误处理策略（design.md §6.1）。

分层异常让上层能按层捕获并决定降级策略；任何失败最终都必须留下日志。
"""

from __future__ import annotations


class SDDError(Exception):
    """本项目所有自定义异常的基类。"""

    def __init__(self, message: str, *, source: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.source = source

    def __str__(self) -> str:
        if self.source:
            return f"[{self.source}] {self.message}"
        return self.message


class CollectorError(SDDError):
    """采集层异常：外部平台不可达、认证失败、数据解析失败等。"""


class GeneratorError(SDDError):
    """生成层异常：数据聚合或模板渲染失败等。"""


class NotifierError(SDDError):
    """推送层异常：邮件 / 飞书机器人发送失败等。"""


class ConfigurationError(SDDError):
    """配置异常：配置文件缺失、格式错误或必填字段缺失。"""
