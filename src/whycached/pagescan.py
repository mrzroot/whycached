"""Look inside the HTML: service workers and sub-resources (no network except via callback)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

SW_REGISTER = re.compile(r"""serviceWorker\s*\.\s*register\(\s*['"`]([^'"`]+)['"`]""")
SW_GUESSES = ["/sw.js", "/service-worker.js", "/serviceworker.js", "/ngsw-worker.js", "/firebase-messaging-sw.js"]
TAG = re.compile(r"""<(script|link)\b([^>]*)>""", re.I)
ATTR = re.compile(r"""([a-zA-Z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")
HASHY = re.compile(r"(?:[.\-_@/])([0-9a-f]{8,}|[0-9A-Za-z_-]{8,}={0,2})(?:[.\-_/]|$)")
HEX = re.compile(r"[0-9a-f]{8,}", re.I)
VERSIONED_Q = re.compile(r"[?&](v|ver|version|hash|h|t|ts|_|cb|rev)=", re.I)


def attrs(s: str) -> Dict[str, str]:
    return {m.group(1).lower(): (m.group(2) or m.group(3) or m.group(4) or "") for m in ATTR.finditer(s)}


def find_assets(html: str, base: str, limit: int = 12) -> List[str]:
    host = urlparse(base).netloc
    seen: List[str] = []
    for m in TAG.finditer(html):
        tag, a = m.group(1).lower(), attrs(m.group(2))
        if tag == "script":
            ref = a.get("src")
        else:
            rel = a.get("rel", "").lower()
            if "stylesheet" not in rel and "modulepreload" not in rel:
                continue
            ref = a.get("href")
        if not ref or ref.startswith("data:"):
            continue
        u = urljoin(base, ref)
        if urlparse(u).netloc != host or u in seen:
            continue
        seen.append(u)
        if len(seen) >= limit:
            break
    return seen


def looks_fingerprinted(url: str) -> bool:
    p = urlparse(url)
    if VERSIONED_Q.search("?" + p.query if p.query else ""):
        return True
    name = p.path.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    return bool(HEX.search(stem)) or bool(re.search(r"[.\-_][A-Za-z0-9_-]{8,}$", stem) and re.search(r"\d", stem))


def registered_sw(html: str, base: str) -> List[str]:
    return [urljoin(base, m.group(1)) for m in SW_REGISTER.finditer(html)]


@dataclass
class SWInfo:
    url: str
    workbox: bool = False
    uses_cache_api: bool = False
    skip_waiting: bool = False
    clients_claim: bool = False
    cache_names: List[str] = field(default_factory=list)
    cache_first: bool = False
    precache_entries: int = 0


def analyse_sw(url: str, js: str) -> SWInfo:
    info = SWInfo(url=url)
    info.workbox = "workbox" in js.lower()
    info.uses_cache_api = bool(re.search(r"\bcaches\s*\.\s*(open|match)\b", js)) or info.workbox
    info.skip_waiting = "skipWaiting" in js
    info.clients_claim = bool(re.search(r"clients\s*\.\s*claim", js))
    info.cache_names = list(dict.fromkeys(re.findall(r"""caches\s*\.\s*open\(\s*['"`]([^'"`]+)['"`]""", js)))[:5]
    for m in re.finditer(r"""(?:CACHE(?:_NAME|_VERSION)?|cacheName|VERSION)\s*=\s*['"`]([^'"`]+)['"`]""", js):
        if m.group(1) not in info.cache_names:
            info.cache_names.append(m.group(1))
    info.cache_first = bool(re.search(r"caches\s*\.\s*match\([^)]*\)\s*\.then", js) or "CacheFirst" in js or "precacheAndRoute" in js)
    info.precache_entries = len(re.findall(r"""revision\s*['"]?\s*:""", js))
    return info
