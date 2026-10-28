"""Known gaps: differences between Moodle and OpenLMS that were reviewed and accepted.

``known-gaps/<course slug>.toml`` lists finding ids with a reason. A failing or warning finding
whose id is listed is reported as a known gap; listed ids that match nothing are "stale".
"""

from __future__ import annotations

import json
import tomllib
from datetime import date
from pathlib import Path

from .. import paths
from ..moodle.model import Course
from .findings import FAIL, GAP, WARN, Finding, KnownGap


def default_path(course: Course) -> Path:
    return paths.gaps_dir() / f"{course.slug}.toml"


def load(path: Path) -> list[KnownGap]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [KnownGap(g["id"], g.get("reason", "")) for g in data.get("gap", [])]


def apply(findings: list[Finding], gaps: list[KnownGap]) -> list[KnownGap]:
    """Downgrade listed findings to known gaps. Returns the entries to remove from the file:
    those that match no finding, and those whose finding now passes ("no longer needed")."""
    by_id = {g.id: g for g in gaps}
    used, passing = set(), set()
    for f in findings:
        gap = by_id.get(f.id)
        if gap is None:
            continue
        if f.status in (FAIL, WARN):
            f.status = GAP
            accepted = (
                " (accepted)" if gap.reason in ("", f.detail) else f" — accepted: {gap.reason}"
            )
            f.detail += accepted
            used.add(f.id)
        else:
            passing.add(f.id)
    stale = []
    for g in gaps:
        if g.id in passing - used:
            stale.append(KnownGap(g.id, f"no longer needed: the check passes ({g.reason})"))
        elif g.id not in used:
            stale.append(g)
    return stale


def render(course: Course, findings: list[Finding], today: date | None = None) -> str:
    lines = [
        f"# Known gaps: {course.fullname} ({course.shortname})",
        "#",
        "# Differences between the Moodle course and OpenLMS that are accepted. `mbz2openlms",
        "# check` reports a matching finding as a known gap instead of a failure or warning.",
        f"# Seeded on {today or date.today()} by `mbz2openlms gaps init` from the Moodle",
        "# backup: the Moodle features with no OpenLMS equivalent. Review each entry: delete",
        "# what is not accepted and edit `reason` (it is shown in the report).",
        "#",
        "# Reviewed by: (name, date)",
        "",
    ]
    for f in findings:
        lines += ["[[gap]]", f"id = {_toml(f.id)}", f"reason = {_toml(f.detail)}", ""]
    return "\n".join(lines)


def _toml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # a JSON string is a valid TOML basic string
