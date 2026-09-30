"""飞书消息采集模块（design.md §2、§4.1）。

通过 IM v1 接口获取指定群在采集窗口内的消息：
- 仅保留包含任一关键词的消息；
- 命中敏感词黑名单的消息直接丢弃；
- 支持 text 与 post 两种消息类型的纯文本提取；
飞书 token 失效时由 LarkClient 自动刷新并重试。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from collector._lark_client import LARK_BASE_URL, LarkClient
from shared.models import MessageRecord

_MESSAGES_PATH = "/open-apis/im/v1/messages"
_MENTION_PLACEHOLDER = re.compile(r"@_user_\d+")


def _to_seconds(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def _from_milliseconds(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _extract_text(msg_type: str, raw_content: str) -> str:
    try:
        content = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return ""

    if msg_type == "text":
        text = content.get("text", "")
        return _MENTION_PLACEHOLDER.sub("", text).strip()

    if msg_type == "post":
        parts: list[str] = []
        # post: {"zh_cn": {"title": ..., "content": [[{"tag":"text","text":...}]]}}
        for locale_payload in content.values():
            if not isinstance(locale_payload, dict):
                continue
            if locale_payload.get("title"):
                parts.append(str(locale_payload["title"]))
            for paragraph in locale_payload.get("content", []):
                for node in paragraph:
                    if isinstance(node, dict) and node.get("tag") == "text":
                        parts.append(node.get("text", ""))
        return " ".join(p.strip() for p in parts if p.strip())

    return ""


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word and word in text for word in words)


def collect(
    chat_id: str,
    keywords: list[str],
    since: datetime,
    until: datetime,
    *,
    app_id_env: str = "LARK_APP_ID",
    app_secret_env: str = "LARK_APP_SECRET",
    base_url: str = LARK_BASE_URL,
    sensitive_words: list[str] | None = None,
    chat_name: str = "",
    timeout: float = 10.0,
    lark_client: LarkClient | None = None,
) -> list[MessageRecord]:
    """获取指定群在 [since, until] 内、命中关键词且不涉及敏感内容的消息。"""

    client = lark_client or LarkClient(
        os.environ.get(app_id_env, ""),
        os.environ.get(app_secret_env, ""),
        base_url=base_url,
        timeout=timeout,
    )

    params = {
        "container_id_type": "chat",
        "container_id": chat_id,
        "start_time": str(_to_seconds(since)),
        "end_time": str(_to_seconds(until)),
        "sort_type": "ByCreateTimeAsc",
        "page_size": 50,
    }

    display_name = chat_name or chat_id
    records: list[MessageRecord] = []
    for item in client.paginate(_MESSAGES_PATH, params):
        if item.get("deleted"):
            continue

        body = item.get("body", {})
        text = _extract_text(item.get("msg_type", ""), body.get("content", ""))
        if not text:
            continue
        if sensitive_words and _contains_any(text, sensitive_words):
            continue
        if keywords and not _contains_any(text, keywords):
            continue

        sender = item.get("sender", {})
        records.append(
            MessageRecord(
                sender=sender.get("id", ""),
                content=text,
                timestamp=_from_milliseconds(item.get("create_time", 0)),
                chat_name=display_name,
            )
        )

    return records
