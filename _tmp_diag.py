"""临时诊断：核对 11:24 消息。"""

import os
from datetime import datetime, timedelta, timezone

from shared.config import load_config
from shared.envfile import load_envfile

load_envfile(".env")

from collector._lark_client import LarkClient
from collector.lark_msg import _contains_any, _extract_text

c = load_config()
cfg = c["lark_message"]
client = LarkClient(
    os.environ.get("LARK_APP_ID", ""),
    os.environ.get("LARK_APP_SECRET", ""),
)

now = datetime.now(tz=timezone.utc)
start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=8)
params = {
    "container_id_type": "chat",
    "container_id": cfg["chat_id"],
    "start_time": str(int(start.timestamp())),
    "end_time": str(int(now.timestamp())),
    "sort_type": "ByCreateTimeAsc",
    "page_size": 50,
}

lark_map = {m["lark"]: m["name"] for m in c.members}
print("当前本地时间:", datetime.now().strftime("%H:%M:%S"))
items = list(client.paginate("/open-apis/im/v1/messages", params))
text_items = [i for i in items if i.get("msg_type") in ("text", "post")]
print("今日文本类消息数:", len(text_items))
for item in text_items:
    sender_id = item.get("sender", {}).get("id", "")
    text = _extract_text(item.get("msg_type", ""), item.get("body", {}).get("content", ""))
    ts = datetime.fromtimestamp(int(item["create_time"]) / 1000, tz=timezone.utc).astimezone()
    who = lark_map.get(sender_id, f"【未映射:{sender_id}】")
    kw_ok = (not cfg["keywords"]) or _contains_any(text, cfg["keywords"])
    sens_ok = not (cfg["sensitive_words"] and _contains_any(text, cfg["sensitive_words"]))
    print(f"  {ts.strftime('%H:%M:%S')} {who}: {text!r}")
    print(f"     关键词命中: {kw_ok} | 敏感词拦截: {not sens_ok} | {'==> 会进日报' if kw_ok and sens_ok else '==> 不会进日报'}")
