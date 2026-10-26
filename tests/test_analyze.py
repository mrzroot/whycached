from whycached.analyze import analyze, bust_url
from whycached import demo

HTML = {"Content-Type": "text/html"}


def levels(rep):
    return [(f.level, f.layer) for f in rep.findings]


def test_bust_url_keeps_query():
    u = bust_url("http://h/p?a=1", "9")
    assert u == "http://h/p?a=1&_whycached=9"


def test_stale_cdn_confirmed(box):
    def route(h):
        if "?" in h.path or "no-cache" in h.headers.get("Cache-Control", ""):
            return 200, dict(HTML, **{"CF-Cache-Status": "MISS", "Server": "cloudflare"}), "NEW v2"
        return 200, dict(HTML, **{"CF-Cache-Status": "HIT", "Server": "cloudflare", "Age": "500", "Cache-Control": "public, max-age=3600"}), "OLD v1"
    box.routes["/"] = route
    rep = analyze(box.base + "/", expect="v2")
    assert ("STALE", "shared") in levels(rep)
    f = next(x for x in rep.findings if x.level == "STALE")
    assert "Cloudflare" in f.title and any("purge" in x.lower() for x in f.fix)
    assert rep.worst == "STALE"


def test_expect_missing_everywhere_is_not_a_cache_problem(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}), "same old")
    rep = analyze(box.base + "/", expect="v9")
    assert ("NOTE", "origin") in levels(rep)
    assert not any(f.level in ("STALE", "LIKELY") for f in rep.findings)


def test_healthy_no_cache_html(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}), "<h1>hi</h1>")
    rep = analyze(box.base + "/")
    assert rep.worst in ("OK", "NOTE")
    assert ("OK", "info") in levels(rep)


def test_browser_heuristic_and_maxage(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "max-age=3600"}), "<h1>x</h1>")
    rep = analyze(box.base + "/")
    assert ("LIKELY", "browser") in levels(rep)


def test_html_cached_a_day_is_flagged(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "public, max-age=86400"}), "<h1>x</h1>")
    rep = analyze(box.base + "/")
    assert any("HTML itself" in f.title for f in rep.findings)


def test_service_worker_with_long_cache(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}),
                                 "<script>navigator.serviceWorker.register('/sw.js')</script>")
    box.routes["/sw.js"] = lambda h: (200, {"Content-Type": "text/javascript", "Cache-Control": "max-age=86400"},
                                      "caches.open('x'); caches.match(e.request).then(r=>r)")
    rep = analyze(box.base + "/")
    sw = next(f for f in rep.findings if f.layer == "service-worker")
    assert sw.level == "LIKELY" and any("no-cache" in x for x in sw.fix)


def test_guessed_sw_is_only_a_note(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}), "<h1>x</h1>")
    box.routes["/sw.js"] = lambda h: (200, {"Content-Type": "text/javascript"}, "caches.open('x')")
    rep = analyze(box.base + "/")
    assert [f.level for f in rep.findings if f.layer == "service-worker"] == ["NOTE"]


def test_unfingerprinted_long_cached_asset(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}), "<script src='/app.js'></script><script src='/b.1a2b3c4d5e.js'></script>")
    long = {"Content-Type": "text/javascript", "Cache-Control": "max-age=31536000"}
    box.routes["/app.js"] = lambda h: (200, long, "1")
    box.routes["/b.1a2b3c4d5e.js"] = lambda h: (200, long, "2")
    rep = analyze(box.base + "/")
    titles = [f.title for f in rep.findings if f.layer == "asset"]
    assert len(titles) == 1 and "/app.js" in titles[0]


def test_no_assets_flag(box):
    box.routes["/"] = lambda h: (200, dict(HTML, **{"Cache-Control": "no-cache"}), "<script src='/app.js'></script>")
    box.routes["/app.js"] = lambda h: (200, {"Cache-Control": "max-age=31536000"}, "1")
    assert not [f for f in analyze(box.base + "/", check_assets=False).findings if f.layer == "asset"]


def test_unreachable_reports_error():
    rep = analyze("http://127.0.0.1:1/", timeout=1)
    assert rep.error and rep.worst == "OK"


def test_demo_scenarios():
    srv, base = demo.start()
    try:
        assert analyze(base + "/shop/", expect="v2").worst == "STALE"
        assert any(f.layer == "service-worker" for f in analyze(base + "/pwa/").findings)
        assert analyze(base + "/docs/").worst == "OK"
    finally:
        srv.shutdown()
