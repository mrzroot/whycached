# Novelty check: whycached

Done 2026-10-24 before building. Wording is deliberately modest: **no existing tool found as of October 2026**
that does what `whycached` does; this is not a claim that none exists anywhere.

What it does that was searched for: given a *live deployed URL*, send comparison requests and say which layer (CDN /
browser / service worker / asset naming) serves the stale copy, with a layer-specific fix.

## GitHub repository search queries (API, total results)

| query | total |
|---|---|
| `whycached` | 0 |
| `why is my site cached` | 2 |
| `cache headers explain` | 8 |
| `cache layer explain cdn` | 0 |
| `stale cdn cache diagnose` | 0 |
| `http cache debugger cli` | 6 |
| `cache-control analyzer` | 0 |
| `github pages cache stale` | 5 |
| `which cache served response` | 6 |
| `age header cf-cache-status x-cache explain` | 0 |
| `cache busting diagnose deployed` | 0 |
| `cache layer cdn browser diagnose` | 0 |
| `cdn stale content cli` | 0 |
| `cache debug cli curl headers verdict` | 0 |
| `x-cache age verdict` | 0 |
| `cache buster explain` | 0 |
| `service worker stale diagnose` | 0 |
| `http cache explain cli` | 3 |

Most queries returned 0 or only unrelated repositories (search is AND-of-terms and noisy). The relevant hits were read:

## Closest existing work (all different in kind)

| project | what it is | difference |
|---|---|---|
| hdrlens (Gulliby-development) | offline CLI that explains a saved header file, including cache freshness | no network, one response; cannot compare layers or find a stale copy |
| freshtrace (qsxustc) | offline browser/CDN cache *policy* lab: paste headers, move through time | simulation from headers you paste; does not fetch or compare |
| cachetape (KanadeK) | replays a scripted request sequence through a cache model, for CI | a simulator of an imagined cache, not a probe of yours |
| httpcache (sandipan-x), cache-control-guru | generate / explain `Cache-Control` values | authoring helpers |
| CacheSweeper | browser extension to clear site data | clears; does not diagnose which layer |
| Cloudflare / Fastly / Vercel docs, blog guides | manual "check X-Cache and Age" checklists | the checklist whycached automates |

Also looked at on the web (no dedicated CLI found for "which cache layer is serving my stale response").

## Verdict

Distinct combination: **live probe + byte comparison across four request variants + per-layer verdict + service-worker and
asset-name analysis + vendor-specific fix**. Individual ingredients (header parsing, freshness maths) are standard and
exist in libraries; the packaged diagnosis does not appear to. If you know of a tool that does this, please open an issue.

## Rejected during the same brainstorm (for the record)

- Cross-library Jalali date disagreement checker: tested jdatetime, persiantools vs ICU for 1900-2100: 100 % agreement, no real problem to solve.
- Database connection staged diagnoser: `holdon` already covers DNS to TCP to TLS to protocol for several databases.
- Flaky-test statistics, GRIM-style metric checks, McNemar CLIs, SMS segment calculators, Persian normalizers: close tools exist.
