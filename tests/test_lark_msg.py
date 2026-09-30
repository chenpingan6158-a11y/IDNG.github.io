"""collector/lark_msg.py 单元测试（Mock LarkClient）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from collector import lark_msg
from shared.models import MessageRecord

_SINCE = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)
_UNTIL = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)
_KEYWORDS = ["上线", "bug"]
_SENSITIVE = ["薪资"]


class FakeLark:
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def paginate(self, path: str, params: dict):
        yield from self._items


def _text_message(text: str, create_ms: int, sender: str = "ou_zhangsan") -> dict:
    return {
        "msg_type": "text",
        "create_time": str(create_ms),
        "deleted": False,
        "sender": {"id": sender},
        "body": {"content": json.dumps({"text": text}, ensure_ascii=False)},
    }


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def test_collect_message_matching_keyword() -> None:
    fake = FakeLark(
        [_text_message("今晚准备上线发布", _ms(_SINCE) + 3600_000)]
    )
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL,
        sensitive_words=_SENSITIVE, chat_name="研发群", lark_client=fake,
    )

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, MessageRecord)
    assert record.sender == "ou_zhangsan"
    assert record.content == "今晚准备上线发布"
    assert record.chat_name == "研发群"


def test_message_without_keyword_is_filtered() -> None:
    fake = FakeLark([_text_message("今天天气不错", _ms(_SINCE) + 1000)])
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL, lark_client=fake
    )
    assert records == []


def test_sensitive_message_is_dropped() -> None:
    fake = FakeLark([_text_message("这个月薪资上线系统调整", _ms(_SINCE) + 1000)])
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL,
        sensitive_words=_SENSITIVE, lark_client=fake,
    )
    assert records == []


def test_deleted_message_is_skipped() -> None:
    item = _text_message("上线", _ms(_SINCE) + 1000)
    item["deleted"] = True
    fake = FakeLark([item])
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL, lark_client=fake
    )
    assert records == []


def test_mention_placeholder_is_stripped() -> None:
    item = _text_message("@_user_1 这个 bug 已修复", _ms(_SINCE) + 1000)
    fake = FakeLark([item])
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL, lark_client=fake
    )
    assert len(records) == 1
    assert "@_user_1" not in records[0].content


def test_post_message_text_extraction() -> None:
    post_content = json.dumps(
        {
            "zh_cn": {
                "title": "发布通知",
                "content": [[{"tag": "text", "text": "服务已上线"}]],
            }
        },
        ensure_ascii=False,
    )
    item = {
        "msg_type": "post",
        "create_time": str(_ms(_SINCE) + 1000),
        "deleted": False,
        "sender": {"id": "ou_lisi"},
        "body": {"content": post_content},
    }
    fake = FakeLark([item])
    records = lark_msg.collect(
        "oc_group", _KEYWORDS, _SINCE, _UNTIL,
        chat_name="研发群", lark_client=fake,
    )
    assert len(records) == 1
    assert "发布通知" in records[0].content
    assert "服务已上线" in records[0].content
