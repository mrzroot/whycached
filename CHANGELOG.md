# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-24

First release.

### Added
- Four probes per URL: normal (twice), cache-busted query, `Cache-Control: no-cache` request, conditional (`If-None-Match`).
- Recognition of Cloudflare, Fastly, GitHub Pages, Vercel, CloudFront, Netlify, Akamai, Azure Front Door, Varnish, nginx/proxy caches and RFC 9211 `Cache-Status`.
- Freshness maths (s-maxage, max-age, Expires, heuristic 10 %, Age) for shared and private caches.
- Browser findings, service-worker analysis (Cache API, Workbox, skipWaiting, long-cached worker script), unversioned long-cached assets.
- `--expect TEXT`, `--json`, `-H`, `--demo`.
