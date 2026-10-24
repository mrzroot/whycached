from whycached import layers
from whycached.fetch import Resp


def R(**h):
    return Resp(url="http://x/", status=200, headers={k.lower().replace("_", "-"): v for k, v in h.items()})


def test_cloudflare_hit():
    s = layers.detect(R(CF_Cache_Status="HIT", Server="cloudflare"))
    assert s[0].layer == "Cloudflare" and s[0].state == "hit"


def test_cloudflare_dynamic_and_revalidated():
    assert layers.detect(R(CF_Cache_Status="DYNAMIC"))[0].state == "dynamic"
    assert layers.detect(R(CF_Cache_Status="REVALIDATED"))[0].state == "revalidated"


def test_github_pages_fastly_list():
    s = layers.detect(R(Server="GitHub.com", X_GitHub_Request_Id="1", X_Cache="MISS, HIT"))
    assert s[0].layer == "GitHub Pages (Fastly)" and s[0].state == "hit"
    s = layers.detect(R(Server="GitHub.com", X_Cache="MISS, MISS"))
    assert s[0].state == "miss"


def test_cloudfront_and_vercel():
    s = layers.detect(R(X_Amz_Cf_Id="a", X_Cache="Hit from cloudfront"))
    assert s[0].layer == "CloudFront" and s[0].state == "hit"
    s = layers.detect(R(X_Vercel_Cache="STALE", X_Vercel_Id="x"))
    assert s[0].layer == "Vercel edge" and s[0].state == "stale"


def test_age_only_means_a_cache_served_it():
    s = layers.detect(R(Age="30"))
    assert s[0].state == "hit"


def test_parse_cc():
    cc = layers.parse_cc('public, max-age=60, s-maxage=300, stale-while-revalidate=30, no-transform')
    assert cc["max-age"] == "60" and cc["s-maxage"] == "300" and "public" in cc


def test_freshness_shared_prefers_s_maxage_and_counts_age():
    f = layers.freshness(R(Cache_Control="max-age=60, s-maxage=300", Age="100"), shared=True)
    assert f.lifetime == 300 and f.remaining == 200 and f.source == "s-maxage"
    f = layers.freshness(R(Cache_Control="max-age=60, s-maxage=300", Age="100"), shared=False)
    assert f.lifetime == 60 and f.remaining == 0


def test_freshness_no_cache_and_no_store():
    assert layers.freshness(R(Cache_Control="no-cache"), False).remaining == 0
    assert layers.freshness(R(Cache_Control="no-store, max-age=100"), False).no_store


def test_freshness_heuristic():
    f = layers.freshness(R(Date="Sat, 24 Oct 2026 10:00:00 GMT", Last_Modified="Fri, 23 Oct 2026 10:00:00 GMT"), False)
    assert f.source == "heuristic" and f.lifetime == 8640


def test_freshness_expires():
    f = layers.freshness(R(Date="Sat, 24 Oct 2026 10:00:00 GMT", Expires="Sat, 24 Oct 2026 11:00:00 GMT"), False)
    assert f.source == "expires" and f.lifetime == 3600


def test_human():
    assert layers.human(45) == "45s" and layers.human(3600) == "60m 00s" and layers.human(None) == "unknown"
