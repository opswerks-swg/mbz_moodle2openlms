"""The OpenLMS course review rules, applied to every unit."""

from __future__ import annotations

from urllib.parse import urlsplit

from .. import review
from ..context import Context
from ..findings import FAIL, PASS, WARN


def run(ctx: Context) -> None:
    host = urlsplit(ctx.moodle.source.wwwroot or "").hostname
    units = [(f"{s.name} › {sub.name} › {u.name}", u.xml) for s, sub, u in ctx.openlms.units()]
    grouped: dict[tuple[str, str], list[review.Issue]] = {}
    for issue in review.scan(units, ctx.rules, host):
        grouped.setdefault((issue.rule, issue.key), []).append(issue)
    for (rule, key), issues in grouped.items():
        places = sorted({i.where for i in issues})
        where = places[0] + (f" (+{len(places) - 1} more)" if len(places) > 1 else "")
        status = FAIL if any(i.severity == "fail" for i in issues) else WARN
        ctx.add(f"review-{rule}|{key}", "review rules", where, status, issues[0].detail)
    detail = f"scanned {len(units)} unit(s) with rules from {ctx.rules.source}"
    ctx.add("review-scan", "review rules", "course", PASS, detail)
