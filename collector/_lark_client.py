"""飞书开放平台客户端（collector 内部共享实现细节，不对外暴露）。

职责：
- 获取并缓存 tenant_access_token，失效时自动刷新并重试一次；
- 统一解析 {"code":0,...} 响应信封；
- 网络超时按调用方给定次数重试；
- 提供分页迭代器。
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from shared.errors import CollectorError
from shared.logger import get_logger

logger = get_logger(__name__)

LARK_BASE_URL = "https://open.feishu.cn"
_TOKEN_PATH = "/open-apis/auth/v3/tenant_access_token/internal"

# tenant_access_token 失效 / 过期相关错误码
_AUTH_ERROR_CODES = {99991661, 99991663, 99991664, 99991668}


class LarkClient:
    """带令牌管理与重试的飞书客户端。"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        base_url: str = LARK_BASE_URL,
        timeout: float = 10.0,
        http_client: Any = None,
        sleeper: Any = time.sleep,
        max_retries: int = 3,
        retry_interval: float = 5.0,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http = http_client or httpx.Client(timeout=timeout)
        self._sleeper = sleeper
        self._max_retries = max_retries
        self._retry_interval = retry_interval
        self._token: str = ""
        self._token_expire_at: float = 0.0

    # ---- 令牌 ----
    def _fetch_token(self) -> None:
        try:
            resp = self._http.request(
                "POST",
                self.base_url + _TOKEN_PATH,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            payload = resp.json()
        except httpx.HTTPError as exc:
            raise CollectorError(f"获取飞书 token 失败：{exc}", source="lark") from exc

        if payload.get("code") != 0:
            raise CollectorError(
                f"获取飞书 token 被拒绝：{payload.get('msg')}", source="lark"
            )
        self._token = payload["tenant_access_token"]
        # 提前 60s 过期，避免临界点失效
        self._token_expire_at = time.time() + int(payload.get("expire", 7200)) - 60

    def _valid_token(self) -> str:
        if not self._token or time.time() >= self._token_expire_at:
            self._fetch_token()
        return self._token

    def refresh_token(self) -> str:
        self._token = ""
        return self._valid_token()

    # ---- 请求 ----
    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """发起一次 API 调用，返回 data 字段；网络错误重试、鉴权失败刷新一次。"""

        url = self.base_url + path
        last_error = ""
        reauthenticated = False

        for attempt in range(1, self._max_retries + 1):
            token = self._valid_token()
            headers = {"Authorization": f"Bearer {token}"}
            try:
                resp = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                payload = resp.json()
            except httpx.HTTPError as exc:
                last_error = f"网络错误：{exc}"
                logger.error(
                    "飞书请求失败，准备重试",
                    extra={"attempt": attempt, "path": path, "error": last_error},
                )
                if attempt < self._max_retries:
                    self._sleeper(self._retry_interval)
                continue

            code = payload.get("code")
            if code == 0:
                return payload.get("data", {})

            last_error = f"code={code}, msg={payload.get('msg')}"
            if code in _AUTH_ERROR_CODES and not reauthenticated:
                logger.error("飞书 token 失效，刷新后重试", extra={"path": path})
                self.refresh_token()
                reauthenticated = True
                continue

            logger.error(
                "飞书接口返回错误",
                extra={"attempt": attempt, "path": path, "error": last_error},
            )
            if attempt < self._max_retries:
                self._sleeper(self._retry_interval)

        raise CollectorError(f"飞书请求最终失败：{last_error}", source="lark")

    def paginate(
        self,
        path: str,
        params: dict | None = None,
        *,
        items_key: str = "items",
    ) -> Iterator[dict]:
        """按 page_token 迭代所有分页中的 items。"""

        page_params = dict(params or {})
        page_params["page_size"] = page_params.get("page_size", 50)

        while True:
            data = self.request("GET", path, params=page_params)
            for item in data.get(items_key, []):
                yield item

            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
            if not page_token:
                break
            page_params["page_token"] = page_token
