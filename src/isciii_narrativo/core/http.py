from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class HttpClient:
    def __init__(self, timeout: float = 20.0, user_agent: str = "isciii-narrativo/0.1.0"):
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json,text/xml,application/xml;q=0.9,*/*;q=0.8",
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.8, min=0.8, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
    )
    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        return self._client.get(url, params=params, headers=headers)
