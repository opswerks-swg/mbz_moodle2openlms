"""Access restrictions on completing another activity -> subsection prerequisites.

Moodle requires the activity completed; for an agreement that means every box ticked, so the
prerequisite needs a minimum score of 100%. Prerequisites aren't in a Studio export: from an
export they are "not checked" and the runbook has a checklist step for them.
"""

from __future__ import annotations

from ...openlms.model import Subsection
from ..context import Context
from ..findings import FAIL, PASS, SKIP, WARN


def run(ctx: Context) -> None:
    course = ctx.openlms
    expected_subs: set[int] = set()
    for cmid, node in ctx.nodes.items():
        act = ctx.moodle.activities[cmid]
        r = act.restriction
        if r is None or not r.flat or not r.completion_cmids():
            continue
        required: list[Subsection] = []
        for req in r.completion_cmids():
            rnode = ctx.nodes.get(req)
            if rnode and rnode.sub is not node.sub and rnode.sub not in required:
                required.append(rnode.sub)
        if not required:
            continue  # same subsection: the unit order keeps it
        expected_subs.add(id(node.sub))
        where = act.where
        current = course.subsection(node.sub.prereq)
        set_to = f"'{current.name}'" if current else "none"
        if len(required) > 1:
            names = ", ".join(f"'{s.name}'" for s in required)
            detail = (
                f"Moodle needs {names} completed; OpenLMS allows one prerequisite per subsection"
            )
            if course.prereqs_known:
                detail += f" (set: {set_to})"
            ctx.add(f"restriction-multi|{where}", "prerequisites", where, FAIL, detail)
            continue
        if not course.prereqs_known:
            detail = (
                f"subsection '{node.sub.name}' should require '{required[0].name}' at 100%: "
                "not in a Studio export, check it in Studio (runbook checklist)"
            )
            ctx.add(f"prereq|{where}", "prerequisites", where, SKIP, detail)
            continue
        fix = {"action": "prereq", "subsection": node.sub.id, "prereq": required[0].id}
        score = node.sub.prereq_min_score
        if current is required[0] and (score is None or score < 100):
            shown = "not set" if score is None else f"{score:g}%"
            detail = (
                f"subsection '{node.sub.name}' requires '{required[0].name}' with minimum score "
                f"{shown}; set it to 100%"
            )
            ctx.add(f"prereq|{where}", "prerequisites", where, FAIL, detail, fix)
        elif current is required[0]:
            detail = f"subsection '{node.sub.name}' requires '{required[0].name}' (100%)"
            ctx.add(f"prereq|{where}", "prerequisites", where, PASS, detail, fix)
        else:
            detail = (
                f"subsection '{node.sub.name}' should require '{required[0].name}', "
                f"OpenLMS prerequisite: {set_to}"
            )
            ctx.add(f"prereq|{where}", "prerequisites", where, FAIL, detail, fix)
    if course.prereqs_known:
        for _section, sub in course.subsections():
            if sub.prereq and id(sub) not in expected_subs:
                where = f"subsection '{sub.name}'"
                detail = "has a prerequisite that Moodle didn't have"
                ctx.add(f"prereq-extra|{sub.name}", "prerequisites", where, WARN, detail)
