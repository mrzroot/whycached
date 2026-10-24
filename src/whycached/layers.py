"""Recognise caching layers from response headers (no network)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from .fetch import Resp


@dataclass
class CacheState:
    layer: str            # "Cloudflare", "Fastly", ...
    state: str            # hit | miss | stale | revalidated | bypass | dynamic | unknown
    raw: str              # header text the state came from
    evidence: str         # human string


def _norm(raw: str) -> str:
    r = raw.lower()
    if "revalidat" in r:
        return "revalidated"
    if "stale" in r or ("expired" in r and "hit" not in r):
        return "stale"
    if "bypass" in r:
        return "bypass"
    if "dynamic" in r or "uncacheable" in r:
        return "dynamic"
    if "hit" in r:
        return "hit"
    if "miss" in r:
        return "miss"
    return "unknown"


def _hit_pattern(raw: str) -> str:
    """Fastly style 'HIT, MISS' lists: any HIT means some node served from cache."""
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if parts and all(p.startswith("miss") for p in parts):
        return "miss"
    if any(p.startswith("hit") for p in parts):
        return "hit"
    return _norm(raw)


def detect(r: Resp) -> List[CacheState]:
    h = r.headers
    out: List[CacheState] = []

    def add(layer, header, state=None):
        raw = h.get(header, "")
        out.append(CacheState(layer, state or _norm(raw), raw, f"{header}: {raw}" if raw else layer))

    server = h.get("server", "").lower()
    via = h.get("via", "").lower()
    xcache = h.get("x-cache", "")

    if "cf-cache-status" in h or "cf-ray" in h or server == "cloudflare":
        add("Cloudflare", "cf-cache-status") if "cf-cache-status" in h else out.append(
            CacheState("Cloudflare", "unknown", "", "cf-ray present, no cf-cache-status"))
    if "x-vercel-cache" in h or "x-vercel-id" in h:
        add("Vercel edge", "x-vercel-cache") if "x-vercel-cache" in h else out.append(
            CacheState("Vercel edge", "unknown", "", "x-vercel-id present"))
    if "x-amz-cf-id" in h or "cloudfront" in via or "cloudfront" in xcache.lower():
        raw = xcache or h.get("x-amz-cf-pop", "")
        out.append(CacheState("CloudFront", _norm(raw), raw, f"X-Cache: {raw}" if raw else "x-amz-cf-id present"))
    if "x-nf-request-id" in h or "netlify" in h.get("cache-status", "").lower() or server == "netlify":
        raw = h.get("cache-status", "")
        out.append(CacheState("Netlify edge", _norm(raw), raw, f"Cache-Status: {raw}" if raw else "x-nf-request-id present"))
    if "x-azure-ref" in h:
        out.append(CacheState("Azure Front Door", _norm(h.get("x-cache", "")), h.get("x-cache", ""), "x-azure-ref present"))
    if "akamai" in server or any(k.startswith("x-akamai") for k in h):
        out.append(CacheState("Akamai", _norm(xcache), xcache, f"X-Cache: {xcache}" if xcache else "akamai headers"))
    fastly = ("x-served-by" in h and "cache-" in h["x-served-by"].lower()) or "x-timer" in h or "fastly" in via
    if server.startswith("github.com") or "x-github-request-id" in h:
        raw = xcache
        s = _hit_pattern(raw) if raw else "unknown"
        out.append(CacheState("GitHub Pages (Fastly)", s, raw, f"X-Cache: {raw}" if raw else "x-github-request-id present"))
    elif fastly:
        raw = xcache
        out.append(CacheState("Fastly", _hit_pattern(raw) if raw else "unknown", raw,
                              f"X-Cache: {raw}" if raw else "x-served-by / x-timer present"))
    if "varnish" in via or "x-varnish" in h:
        if not any(c.layer in ("Fastly", "GitHub Pages (Fastly)") for c in out):
            out.append(CacheState("Varnish", _hit_pattern(xcache) if xcache else "unknown", xcache,
                                  f"X-Cache: {xcache}" if xcache else "x-varnish present"))
    for name in ("x-cache-status", "x-proxy-cache", "x-nginx-cache"):
        if name in h:
            out.append(CacheState("nginx/proxy cache", _norm(h[name]), h[name], f"{name}: {h[name]}"))
    rfc = h.get("cache-status", "")
    if rfc and not any("Netlify" in c.layer for c in out):
        first = rfc.split(",")[0]
        state = "hit" if re.search(r";\s*hit\b", rfc, re.I) else ("miss" if "fwd=" in rfc else "unknown")
        out.append(CacheState(first.split(";")[0].strip() or "cache", state, rfc, f"Cache-Status: {rfc}"))
    if not out and "age" in h:
        out.append(CacheState("unknown shared cache", "hit", f"Age: {h['age']}", f"Age: {h['age']} (a cache served this)"))
    return out


# ------------------------------------------------------------- freshness

def parse_cc(value: str) -> Dict[str, Optional[str]]:
    d: Dict[str, Optional[str]] = {}
    for part in re.split(r",\s*(?=[A-Za-z-]+(?:=|,|$))", value or ""):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            d[k.strip().lower()] = v.strip().strip('"')
        else:
            d[part.lower()] = None
    return d


def _int(v: Optional[str]) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


@dataclass
class Freshness:
    lifetime: Optional[int]   # seconds, None = unknown
    source: str               # max-age | s-maxage | expires | heuristic | none
    age: int
    remaining: Optional[int]
    must_revalidate: bool     # no-cache / no-store: caches must ask before reuse
    no_store: bool
    immutable: bool


def freshness(r: Resp, shared: bool, now_epoch: Optional[float] = None) -> Freshness:
    from email.utils import parsedate_to_datetime
    cc = parse_cc(r.h("cache-control"))
    age = _int(r.h("age")) or 0
    no_store = "no-store" in cc
    must = "no-cache" in cc
    immutable = "immutable" in cc
    lifetime, src = None, "none"
    if shared and _int(cc.get("s-maxage")) is not None:
        lifetime, src = _int(cc["s-maxage"]), "s-maxage"
    elif _int(cc.get("max-age")) is not None:
        lifetime, src = _int(cc["max-age"]), "max-age"
    elif r.h("expires") and r.h("date"):
        try:
            lifetime = int((parsedate_to_datetime(r.h("expires")) - parsedate_to_datetime(r.h("date"))).total_seconds())
            src = "expires"
        except Exception:
            pass
    if lifetime is None and r.h("last-modified") and r.h("date") and not (no_store or must):
        try:
            delta = (parsedate_to_datetime(r.h("date")) - parsedate_to_datetime(r.h("last-modified"))).total_seconds()
            if delta > 0:
                lifetime, src = int(delta * 0.1), "heuristic"
        except Exception:
            pass
    remaining = None if lifetime is None else max(0, lifetime - age)
    if no_store or must:
        remaining = 0
    return Freshness(lifetime, src, age, remaining, must, no_store, immutable)


def human(sec: Optional[int]) -> str:
    if sec is None:
        return "unknown"
    if sec < 90:
        return f"{sec}s"
    if sec < 5400:
        return f"{sec // 60}m {sec % 60:02d}s"
    if sec < 172800:
        return f"{sec // 3600}h {(sec % 3600) // 60:02d}m"
    return f"{sec // 86400}d {(sec % 86400) // 3600}h"
