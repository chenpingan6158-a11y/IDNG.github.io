"""shared/errors.py 单元测试。"""

from __future__ import annotations

import pytest

from shared.errors import (
    CollectorError,
    ConfigurationError,
    GeneratorError,
    NotifierError,
    SDDError,
)


@pytest.mark.parametrize(
    "error_cls",
    [CollectorError, GeneratorError, NotifierError, ConfigurationError],
)
def test_layer_errors_inherit_base(error_cls: type[SDDError]) -> None:
    error = error_cls("出错了", source="unit")
    assert isinstance(error, SDDError)
    assert error.message == "出错了"
    assert error.source == "unit"
    assert str(error) == "[unit] 出错了"


def test_error_without_source() -> None:
    assert str(CollectorError("plain")) == "plain"
