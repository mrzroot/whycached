from whycached import pagescan as ps


def test_find_assets_same_origin_only():
    html = ("<link rel=stylesheet href='/a.css'><script src=\"https://cdn.x/y.js\"></script>"
            "<script src=app.js></script><link rel=icon href=/f.ico>")
    assert ps.find_assets(html, "http://h/p/") == ["http://h/a.css", "http://h/p/app.js"]


def test_fingerprint_detection():
    assert ps.looks_fingerprinted("http://h/app.9b2d44aa.js")
    assert ps.looks_fingerprinted("http://h/app.js?v=3")
    assert ps.looks_fingerprinted("http://h/assets/index-Dk3fJ9aQ.js")
    assert not ps.looks_fingerprinted("http://h/static/app.js")
    assert not ps.looks_fingerprinted("http://h/css/style.css")


def test_registered_sw_relative():
    assert ps.registered_sw("<script>navigator.serviceWorker.register('sw.js')</script>", "http://h/a/") == ["http://h/a/sw.js"]


def test_analyse_sw():
    js = "const CACHE_NAME='v7'; self.skipWaiting(); caches.open('app-v7'); caches.match(e.request).then(r=>r)"
    i = ps.analyse_sw("u", js)
    assert i.uses_cache_api and i.skip_waiting and i.cache_first and "app-v7" in i.cache_names and "v7" in i.cache_names
    assert not ps.analyse_sw("u", "self.addEventListener('push',()=>{})").uses_cache_api
