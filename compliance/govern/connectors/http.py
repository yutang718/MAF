"""HTTP plumbing shared by the REST connectors: retries, throttling, paging."""
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from govern.connectors.base import SourceUnavailable
from govern.log import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 4
MAX_RETRY_WAIT = 60


class ApiClient:
    def __init__(self, base_url: str, auth_headers: Callable[[], dict[str, str]], *,
                 timeout: float = 30.0, transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.base_url = base_url.rstrip("/")
        self._auth_headers = auth_headers
        self._client = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False)
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = self.url(path)
        for attempt in range(MAX_RETRIES + 1):
            headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
            try:
                resp = self._client.request(method, url, headers=headers, **kwargs)
            except httpx.TransportError:
                if attempt == MAX_RETRIES:
                    raise
                self._sleep(2 ** attempt)
                continue
            if resp.status_code == 429 or resp.status_code >= 500 or _secondary_rate_limited(resp):
                if attempt == MAX_RETRIES:
                    break
                wait = _retry_after(resp, attempt)
                logger.info(f"{resp.status_code} from {url}; retrying in {wait:.0f}s")
                self._sleep(wait)
                continue
            break
        return resp

    def get_json(self, path: str, **kwargs) -> Any:
        resp = self.request("GET", path, **kwargs)
        raise_for_source(resp)
        return resp.json()


def _secondary_rate_limited(resp: httpx.Response) -> bool:
    # GitHub signals its secondary limit with 403 plus a zero remaining quota or retry-after.
    return resp.status_code == 403 and (
        resp.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in resp.headers)


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    header = resp.headers.get("retry-after")
    if header and header.isdigit():
        return min(float(header), MAX_RETRY_WAIT)
    reset = resp.headers.get("x-ratelimit-reset")
    if reset and reset.isdigit():
        return min(max(float(reset) - time.time(), 1.0), MAX_RETRY_WAIT)
    return min(2.0 ** attempt, MAX_RETRY_WAIT)


def raise_for_source(resp: httpx.Response) -> None:
    """403/404 on a read means this tenant or token can't see it — not a control failure."""
    if resp.status_code in (401,):
        raise PermissionError(f"authentication rejected ({resp.status_code}): {_message(resp)}")
    if resp.status_code in (402, 403, 404):
        raise SourceUnavailable(f"HTTP {resp.status_code}: {_message(resp)}")
    resp.raise_for_status()


def _message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or err.get("code") or err)[:300]
        return str(body.get("message") or err or body)[:300]
    return str(body)[:300]


def link_next(resp: httpx.Response) -> str | None:
    """RFC 5988 Link header, as used by GitHub and GitLab."""
    return resp.links.get("next", {}).get("url")


def paginate_link(client: ApiClient, path: str, params: dict | None = None,
                  limit: int | None = None, item_key: str | None = None) -> Iterator[dict]:
    url: str | None = path
    count = 0
    first = True
    while url:
        resp = client.request("GET", url, params=params if first else None)
        first = False
        raise_for_source(resp)
        body = resp.json()
        items = body.get(item_key, []) if item_key else body
        for item in items:
            yield item
            count += 1
            if limit is not None and count >= limit:
                return
        url = link_next(resp)
