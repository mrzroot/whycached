"""Run the probes and turn them into findings."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import layers, pagescan
from .fetch import Resp, fetch

FIXES = {
    "Cloudflare": [
        "Dashboard > Caching > Configuration > Purge Cache > Custom Purge > the URL",
        'curl -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE/purge_cache" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data \'{"files":["%(url)s"]}\'',
    ],
    "Fastly": ['curl -X PURGE "%(url)s"   # works if your Fastly service allows PURGE, or purge from the Fastly UI'],
    "GitHub Pages (Fastly)": [
        "GitHub Pages sends Cache-Control: max-age=600 and you cannot purge it: wait for Age to pass 600s (at most 10 minutes), or test with %(bust)s",
        "make sure the Pages build itself finished: repo > Actions > pages build and deployment",
    ],
    "Vercel edge": ["redeploy (a new deployment invalidates the edge cache) or purge from Project > Settings > Caches"],
    "CloudFront": ['aws cloudfront create-invalidation --distribution-id $DIST --paths "%(path)s"'],
    "Netlify edge": ["trigger a deploy (Netlify invalidates its edge cache on every deploy) or use 'Clear cache and deploy site'"],
    "Akamai": ["purge the URL in Akamai Control Center (Fast Purge) or via the Fast Purge API"],
    "Azure Front Door": ["az afd endpoint purge --content-paths \"%(path)s\" --profile-name $PROFILE --endpoint-name $EP --resource-group $RG"],
    "Varnish": ['curl -X PURGE "%(url)s"   # if your VCL accepts PURGE, otherwise ban from varnishadm'],
    "nginx/proxy cache": ["delete the cache file for the key or add 'proxy_cache_bypass $arg_nocache' and request ?nocache=1"],
}


@dataclass
class Finding:
    level: str            # STALE | LIKELY | NOTE | OK
    layer: str            # shared | browser | service-worker | asset | origin | info
    title: str
    why: List[str] = field(default_factory=list)
    fix: List[str] = field(default_factory=list)

    def as_dict(self):
        return {"level": self.level, "layer": self.layer, "title": self.title, "why": self.why, "fix": self.fix}


@dataclass
class Report:
    url: str
    findings: List[Finding] = field(default_factory=list)
    probes: Dict[str, dict] = field(default_factory=dict)
    cdn: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def worst(self) -> str:
        order = ["STALE", "LIKELY", "NOTE", "OK"]
        for lvl in order:
            if any(f.level == lvl for f in self.findings):
                return lvl
        return "OK"


def bust_url(url: str, nonce: Optional[str] = None) -> str:
    p = urlparse(url)
    q = parse_qsl(p.query, keep_blank_values=True) + [("_whycached", nonce or str(int(time.time())))]
    return urlunparse(p._replace(query=urlencode(q)))


def _snap(r: Resp) -> dict:
    return {"status": r.status, "sha": r.sha, "bytes": len(r.body), "etag": r.h("etag"), "last_modified": r.h("last-modified"),
            "age": r.h("age"), "cache_control": r.h("cache-control"), "elapsed_ms": r.elapsed_ms, "url": r.url,
            "cache": [c.evidence for c in layers.detect(r)]}


def analyze(url: str, headers: Optional[Dict[str, str]] = None, expect: Optional[str] = None,
            check_assets: bool = True, timeout: float = 15.0,
            fetcher: Callable[..., Resp] = fetch) -> Report:
    rep = Report(url=url)
    hdr = dict(headers or {})
    plain = fetcher(url, headers=hdr, timeout=timeout)
    if not plain.ok:
        rep.error = plain.error or "no response"
        return rep
    rep.probes["plain"] = _snap(plain)
    again = fetcher(url, headers=hdr, timeout=timeout)
    rep.probes["plain2"] = _snap(again)
    bu = bust_url(url)
    busted = fetcher(bu, headers=hdr, timeout=timeout)
    rep.probes["query-bust"] = _snap(busted)
    nc_headers = dict(hdr, **{"Cache-Control": "no-cache", "Pragma": "no-cache"})
    revalid = fetcher(url, headers=nc_headers, timeout=timeout)
    rep.probes["no-cache-request"] = _snap(revalid)

    states = layers.detect(plain)
    rep.cdn = [s.layer for s in states]
    shared_fr = layers.freshness(plain, shared=True)
    priv_fr = layers.freshness(plain, shared=False)
    path = urlparse(url).path or "/"

    # ---- 1. shared cache vs origin ------------------------------------------------
    differs_q = busted.ok and busted.status == plain.status and busted.sha != plain.sha
    differs_nc = revalid.ok and revalid.status == plain.status and revalid.sha != plain.sha
    exp_plain = exp_fresh = None
    if expect is not None:
        exp_plain = expect in plain.text
        exp_fresh = expect in busted.text or expect in revalid.text
    served_by_cache = any(s.state in ("hit", "stale") for s in states) or (plain.h("age") not in ("", "0"))

    if differs_q or differs_nc or (expect is not None and exp_fresh and not exp_plain):
        who = ", ".join(rep.cdn) or "a cache between you and the origin"
        why = []
        if differs_q:
            why.append(f"the normal response (sha {plain.sha}) differs from the cache-busted one (?_whycached=…, sha {busted.sha})")
        if differs_nc:
            why.append(f"a request with 'Cache-Control: no-cache' returns different content (sha {revalid.sha}) than the normal one (sha {plain.sha})")
        if expect is not None:
            why.append(f"'{expect}' is {'present' if exp_plain else 'MISSING'} in the normal response and "
                       f"{'present' if exp_fresh else 'missing'} in the fresh one")
        if plain.h("age"):
            why.append(f"Age: {plain.h('age')} = the copy you got is {layers.human(shared_fr.age)} old")
        if shared_fr.lifetime is not None:
            why.append(f"it stays fresh for {layers.human(shared_fr.lifetime)} ({shared_fr.source}); about {layers.human(shared_fr.remaining)} left")
        for s in states:
            why.append(f"{s.layer}: {s.evidence}")
        fix = []
        for s in states:
            for f in FIXES.get(s.layer, []):
                fix.append(f % {"url": url, "path": path, "bust": bu})
        if not fix:
            fix.append("purge the URL at whatever CDN/proxy sits in front of the origin, or test with " + bu)
        fix.append("long term: send 'Cache-Control: no-cache' (or a short s-maxage) on the HTML, and put a content hash in asset file names")
        rep.findings.append(Finding("STALE", "shared", f"a shared cache ({who}) is serving an older copy than the origin", why, fix))
    elif expect is not None and not (exp_plain or exp_fresh):
        rep.findings.append(Finding("NOTE", "origin", f"'{expect}' is not in any response, cached or not",
                                    ["neither the normal, cache-busted nor no-cache responses contain it: this is not a caching problem",
                                     "the deploy may not have finished, may have gone to a different environment, or the build output does not contain it"],
                                    ["check which build/commit the server runs (a /version endpoint, build id in the HTML) and that the deploy finished"]))
    elif served_by_cache and (busted.ok and busted.sha == plain.sha):
        rep.findings.append(Finding("OK", "shared", "a shared cache served this response, but it is identical to the origin's",
                                    [f"{s.layer}: {s.evidence}" for s in states] + [f"normal and cache-busted bodies match (sha {plain.sha})"], []))

    if plain.h("age") not in ("", "0") and plain.h("last-modified") and busted.ok and busted.h("last-modified") and plain.h("last-modified") != busted.h("last-modified") and not differs_q:
        rep.findings.append(Finding("NOTE", "shared", "Last-Modified differs between cached and fresh copy although the body is identical",
                                    [f"cached: {plain.h('last-modified')}", f"fresh:  {busted.h('last-modified')}"], []))

    # ---- 2. conditional request -------------------------------------------------------
    if plain.h("etag") or plain.h("last-modified"):
        ch = dict(hdr)
        if plain.h("etag"):
            ch["If-None-Match"] = plain.h("etag")
        else:
            ch["If-Modified-Since"] = plain.h("last-modified")
        cond = fetcher(url, headers=ch, timeout=timeout)
        rep.probes["conditional"] = _snap(cond)
        if cond.ok and cond.status == 200 and cond.sha == plain.sha and not plain.h("etag").startswith("W/"):
            rep.findings.append(Finding("NOTE", "origin", "the server ignores If-None-Match / If-Modified-Since",
                                        [f"sent the ETag/Last-Modified back and still got 200 with the same {len(cond.body)} bytes instead of 304"],
                                        ["harmless for correctness, but browsers re-download on every revalidation"]))

    # ---- 3. browser (private) cache -----------------------------------------------------
    if priv_fr.no_store:
        pass
    elif priv_fr.remaining and priv_fr.remaining > 0 and not priv_fr.must_revalidate:
        lvl = "LIKELY" if (shared_fr.lifetime or 0) >= 60 else "NOTE"
        why = [f"Cache-Control: {plain.h('cache-control') or '(none)'}"]
        if priv_fr.source == "heuristic":
            why = [f"no Cache-Control/Expires, but Last-Modified is {layers.human(int(priv_fr.lifetime * 10))} old, so browsers pick a heuristic freshness of ~10% = {layers.human(priv_fr.lifetime)}"]
        why.append(f"a browser may reuse its stored copy of this URL for up to {layers.human(priv_fr.remaining)} more without asking the server at all")
        if priv_fr.immutable:
            why.append("'immutable': browsers will not even revalidate on reload")
        gh = "GitHub Pages (Fastly)" in rep.cdn
        last = ("GitHub Pages fixes this header at max-age=600 and cannot be changed: a deploy is fully visible to everyone within about 10 minutes"
                if gh else "fix for users: send 'Cache-Control: no-cache' (revalidate every time, still cheap with ETag) on the HTML")
        rep.findings.append(Finding(lvl, "browser", "your browser can legitimately keep showing the old copy", why,
                                    ["hard reload: Ctrl+Shift+R (Cmd+Shift+R on macOS), or DevTools > Network > 'Disable cache' while it is open",
                                     "or test in a private window; or open " + bu, last]))

    # ---- 4. HTML + sub-resources + service worker -------------------------------------------
    ctype = plain.h("content-type").lower()
    html = plain.text if ("html" in ctype or plain.text.lstrip().lower().startswith(("<!doctype", "<html"))) else ""
    base = plain.url
    if html:
        sws = pagescan.registered_sw(html, base)
        guesses = [] if sws else [urlparse(base)._replace(path=g, query="", params="", fragment="").geturl() for g in pagescan.SW_GUESSES]
        found: List[tuple] = []
        for cand in (sws or guesses):
            r = fetcher(cand, headers=hdr, timeout=timeout)
            if r.ok and r.status == 200 and ("javascript" in r.h("content-type").lower() or "serviceWorker" in r.text or "self.addEventListener" in r.text):
                found.append((cand, r, cand in sws))
            if found and not sws:
                break
        for cand, r, registered in found:
            info = pagescan.analyse_sw(cand, r.text)
            rep.probes["service-worker"] = {"url": cand, "registered_in_html": registered, "workbox": info.workbox,
                                            "cache_api": info.uses_cache_api, "skipWaiting": info.skip_waiting,
                                            "cache_names": info.cache_names, "cache_control": r.h("cache-control")}
            why = [f"{cand} " + ("is registered by the page" if registered else "exists (not found in the HTML, so it may be registered by a script)")]
            if info.uses_cache_api:
                why.append("it uses the Cache API" + (" (Workbox)" if info.workbox else "") + (f"; cache names: {', '.join(info.cache_names)}" if info.cache_names else ""))
            if info.cache_first:
                why.append("cache-first/precache strategy: it answers from its own cache BEFORE the network, so no HTTP header above matters for those requests")
            if not info.skip_waiting:
                why.append("no skipWaiting(): a new worker waits until every tab of the site is closed")
            sw_fr = layers.freshness(r, shared=False)
            lvl = "LIKELY" if (info.uses_cache_api and registered) else "NOTE"
            fix = ["DevTools > Application > Service Workers > Unregister (and tick 'Update on reload'); Application > Storage > Clear site data",
                   "change the cache name/version string in the worker so old caches are deleted in the 'activate' event"]
            if sw_fr.remaining and sw_fr.remaining > 0 and sw_fr.lifetime and sw_fr.lifetime >= 3600:
                lvl = "LIKELY" if registered else "NOTE"
                why.append(f"the worker script itself has Cache-Control: {r.h('cache-control')}: it can be re-fetched from HTTP cache for {layers.human(sw_fr.remaining)}, so updates are delayed")
                fix.insert(0, "serve the service-worker file with 'Cache-Control: no-cache' (never a long max-age)")
            rep.findings.append(Finding(lvl, "service-worker", "a service worker may be answering from its own cache", why, fix))

        if check_assets:
            for a in pagescan.find_assets(html, base):
                r = fetcher(a, headers=hdr, timeout=timeout)
                if not r.ok:
                    continue
                fr = layers.freshness(r, shared=False)
                fp = pagescan.looks_fingerprinted(a)
                rep.probes.setdefault("assets", {})[a] = {"cache_control": r.h("cache-control"), "fingerprinted": fp, "status": r.status}
                if fr.lifetime and fr.lifetime >= 86400 and not fp and not fr.immutable:
                    rep.findings.append(Finding("LIKELY", "asset", f"{urlparse(a).path or a} is cached for {layers.human(fr.lifetime)} under a name that never changes",
                                                [f"Cache-Control: {r.h('cache-control')}", "the URL has no content hash or version, so after a deploy browsers keep the old file until it expires"],
                                                ["rename on change (app.3f9a1c.js) or add ?v=<hash>; or shorten max-age and use ETag revalidation"]))
        if (shared_fr.lifetime or 0) >= 86400 and not priv_fr.must_revalidate:
            rep.findings.append(Finding("LIKELY", "browser", f"the HTML itself is cacheable for {layers.human(shared_fr.lifetime)}",
                                        [f"Cache-Control: {plain.h('cache-control')}", "pages that reference new asset names are not picked up until this expires"],
                                        ["HTML should be 'Cache-Control: no-cache' (or a few minutes); only fingerprinted assets deserve long lifetimes"]))

    if not any(f.level in ("STALE", "LIKELY") for f in rep.findings) and not any(f.level == "OK" for f in rep.findings):
        rep.findings.append(Finding("OK", "info", "no caching layer found that would explain an old version",
                                    ["normal, repeated, cache-busted and no-cache requests all return the same content",
                                     "Cache-Control: " + (plain.h("cache-control") or "(none)")],
                                    ["if you still see an old version, check you are on the right URL/environment and that the deploy finished"]))
    return rep
