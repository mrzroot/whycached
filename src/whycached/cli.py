from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .analyze import analyze
from .render import as_json, text


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="whycached", description="Which cache layer is serving you the old version of this URL?")
    ap.add_argument("url", nargs="?", help="the deployed URL you are seeing the old version of")
    ap.add_argument("--expect", metavar="TEXT", help="a string that should be in the NEW version (e.g. a version number)")
    ap.add_argument("-H", "--header", action="append", default=[], metavar="'Name: value'", help="extra request header (repeatable)")
    ap.add_argument("--no-assets", action="store_true", help="do not fetch linked CSS/JS to check their cache headers")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("-v", "--verbose", action="store_true", help="show every probe")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--demo", action="store_true", help="run against a local simulated server (offline)")
    ap.add_argument("--version", action="version", version=f"whycached {__version__}")
    a = ap.parse_args(argv)
    color = sys.stdout.isatty() and not a.no_color

    if a.demo:
        from .demo import run
        sys.stdout.write(run(color=color))
        return 0
    if not a.url:
        ap.error("give a URL, or use --demo")
    url = a.url if "://" in a.url else "https://" + a.url
    hdrs = {}
    for h in a.header:
        if ":" not in h:
            ap.error(f"bad header {h!r}, expected 'Name: value'")
        k, v = h.split(":", 1)
        hdrs[k.strip()] = v.strip()
    rep = analyze(url, headers=hdrs, expect=a.expect, check_assets=not a.no_assets, timeout=a.timeout)
    sys.stdout.write((as_json(rep) + "\n") if a.json else text(rep, color=color, verbose=a.verbose))
    if rep.error:
        return 2
    return 1 if rep.worst in ("STALE", "LIKELY") else 0


if __name__ == "__main__":
    raise SystemExit(main())
