"""Tiny HTTP client built on urllib: records headers, redirects and body hash."""
from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MAX_BODY = 2_000_000
DEFAULT_UA = "whycached/0.1 (+https://github.com/mrzroot/whycached)"


@dataclass
class Resp:
    url: str
    status: int = 0
    headers: Dict[str, str] = field(default_factory=dict)  # lower-case name -> joined value
    body: bytes = b""
    redirects: List[Tuple[int, str]] = field(default_factory=list)
    elapsed_ms: int = 0
    error: Optional[str] = None

    def h(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.body).hexdigest()[:12]

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    @property
    def ok(self) -> bool:
        return self.error is None and self.status > 0


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain: List[Tuple[int, str]] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _NoProxyHTTP(urllib.request.ProxyHandler):
    pass


def fetch(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 15.0,
          method: str = "GET") -> Resp:
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "*/*", "Accept-Encoding": "identity"}
    hdrs.update(headers or {})
    red = _Redirects()
    opener = urllib.request.build_opener(red)
    req = urllib.request.Request(url, headers=hdrs, method=method)
    t0 = time.time()
    r = Resp(url=url)
    try:
        with opener.open(req, timeout=timeout) as resp:
            _fill(r, resp, resp.status)
    except urllib.error.HTTPError as e:  # 304, 404, 5xx still carry headers
        _fill(r, e, e.code)
    except Exception as e:  # network / TLS / timeout
        r.error = f"{type(e).__name__}: {e}"
    r.redirects = red.chain
    r.elapsed_ms = int((time.time() - t0) * 1000)
    return r


def _fill(r: Resp, resp, status: int) -> None:
    r.status = status
    r.url = getattr(resp, "url", None) or getattr(resp, "geturl", lambda: r.url)()
    joined: Dict[str, List[str]] = {}
    for k, v in resp.headers.items():
        joined.setdefault(k.lower(), []).append(v)
    r.headers = {k: ", ".join(v) for k, v in joined.items()}
    try:
        r.body = resp.read(MAX_BODY)
    except Exception:
        r.body = b""
