from __future__ import annotations

import json
import sys
from typing import List

from . import __version__
from .analyze import Report

MARK = {"STALE": "✗", "LIKELY": "!", "NOTE": "·", "OK": "✓"}


def _c(txt: str, code: str, on: bool) -> str:
    return f"\033[{code}m{txt}\033[0m" if on else txt


def text(rep: Report, color: bool = False, verbose: bool = False) -> str:
    out: List[str] = [f"whycached {__version__} · {rep.url}"]
    if rep.error:
        out.append(f"error: could not fetch: {rep.error}")
        return "\n".join(out)
    p = rep.probes["plain"]
    out.append(f"HTTP {p['status']} · {p['bytes']} bytes · sha {p['sha']}" + (f" · layers: {', '.join(rep.cdn)}" if rep.cdn else " · no CDN headers seen"))
    if verbose:
        for k in ("plain", "plain2", "query-bust", "no-cache-request", "conditional"):
            if k in rep.probes:
                q = rep.probes[k]
                out.append(f"  {k:<17} {q['status']} sha {q['sha']} age={q['age'] or '-'} etag={q['etag'] or '-'} {' | '.join(q['cache'])}")
    out.append("")
    colors = {"STALE": "31", "LIKELY": "33", "NOTE": "36", "OK": "32"}
    for lvl in ("STALE", "LIKELY", "NOTE", "OK"):
        fs = [f for f in rep.findings if f.level == lvl]
        if not fs:
            continue
        out.append(_c(f"{lvl} ({len(fs)})", colors[lvl], color))
        out.append("")
        for f in fs:
            out.append(f"{_c(MARK[lvl], colors[lvl], color)} {f.layer} · {f.title}")
            for i, w in enumerate(f.why):
                out.append(f"    {'why:  ' if i == 0 else '      '}  {w}")
            for i, x in enumerate(f.fix):
                out.append(f"    {'fix:  ' if i == 0 else '      '}  {x}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def as_json(rep: Report) -> str:
    return json.dumps({"url": rep.url, "error": rep.error, "worst": rep.worst, "layers": rep.cdn,
                       "probes": rep.probes, "findings": [f.as_dict() for f in rep.findings]}, indent=2, ensure_ascii=False)
