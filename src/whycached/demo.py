"""Offline demo: a local server that behaves like three differently broken deployments."""
from __future__ import annotations

import http.server
import threading
from typing import Dict, Tuple

from .analyze import analyze
from .render import text

HOME_V1 = "<!doctype html><title>Shop</title><h1>Shop v1 (old)</h1>"
HOME_V2 = "<!doctype html><title>Shop</title><h1>Shop v2 (new checkout)</h1>"

PWA = ("<!doctype html><title>PWA</title><link rel=stylesheet href='/static/app.css'>"
       "<script src='/static/app.js'></script>"
       "<script>navigator.serviceWorker.register('/pwa/sw.js')</script><h1>PWA</h1>")
SW = ("const CACHE_NAME = 'pwa-v1';\n"
      "self.addEventListener('install', e => e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(['/', '/static/app.js']))));\n"
      "self.addEventListener('fetch', e => e.respondWith(caches.match(e.request).then(r => r || fetch(e.request))));\n")

HEALTHY = ("<!doctype html><title>Docs</title><link rel=stylesheet href='/assets/site.3f9a1c7e.css'>"
           "<script src='/assets/app.9b2d44aa.js'></script><h1>Docs</h1>")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body: str, headers: Dict[str, str], status: int = 200):
        data = body.encode()
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        bypass = bool(query) or "no-cache" in self.headers.get("Cache-Control", "")
        if path == "/shop/":
            if bypass:  # reached the origin
                return self._send(HOME_V2, {"Content-Type": "text/html", "Cache-Control": "public, max-age=14400",
                                            "CF-Cache-Status": "MISS", "CF-RAY": "8a1b2c3d4e5f-FRA", "Server": "cloudflare"})
            return self._send(HOME_V1, {"Content-Type": "text/html", "Cache-Control": "public, max-age=14400", "Age": "4120",
                                        "CF-Cache-Status": "HIT", "CF-RAY": "8a1b2c3d4e5f-FRA", "Server": "cloudflare"})
        if path == "/pwa/":
            return self._send(PWA, {"Content-Type": "text/html", "Cache-Control": "no-cache"})
        if path == "/pwa/sw.js":
            return self._send(SW, {"Content-Type": "application/javascript", "Cache-Control": "public, max-age=86400"})
        if path.startswith("/static/"):
            return self._send("/* asset */", {"Content-Type": "text/css" if path.endswith(".css") else "application/javascript",
                                              "Cache-Control": "public, max-age=31536000"})
        if path == "/docs/":
            if self.headers.get("If-None-Match") == '"docs-1"':
                return self._send("", {"ETag": '"docs-1"', "Cache-Control": "no-cache"}, 304)
            return self._send(HEALTHY, {"Content-Type": "text/html", "Cache-Control": "no-cache", "ETag": '"docs-1"'})
        if path.startswith("/assets/"):
            return self._send("/* hashed */", {"Content-Type": "text/css" if path.endswith(".css") else "application/javascript",
                                               "Cache-Control": "public, max-age=31536000, immutable"})
        self._send("not found", {"Content-Type": "text/plain"}, 404)


def start() -> Tuple[http.server.ThreadingHTTPServer, str]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def run(color: bool = False) -> str:
    srv, base = start()
    try:
        parts = []
        for title, path, kw in [
            ("1. 'I deployed v2 but still see v1' (a CDN in front, simulated)", "/shop/", {"expect": "v2"}),
            ("2. a PWA whose changes never show up", "/pwa/", {}),
            ("3. a healthy deployment", "/docs/", {}),
        ]:
            parts.append(f"$ whycached {base}{path}" + (f" --expect {kw['expect']}" if kw else ""))
            parts.append(text(analyze(base + path, **kw), color=color))
        return "\n".join(parts)
    finally:
        srv.shutdown()
