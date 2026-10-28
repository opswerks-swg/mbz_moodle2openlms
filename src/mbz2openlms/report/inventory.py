"""``inventory.md``: what is in a Moodle backup and how it maps. No answer keys."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

from ..mapping import GAP, PARTIAL, QTYPE_GAP, QTYPES, map_activity
from ..moodle.model import Course, QuizDetail
from . import date, table

EMBEDS = ("iframe", "embed", "object")
STATUS = {"supported": "✅ supported", "partial": "⚠️ partial", "gap": "❌ gap", "n/a": "—"}


def render(course: Course) -> str:
    acts = course.activities.values()
    questions = course.bank.latest_questions()
    lines = [
        f"# Inventory: {course.fullname} ({course.shortname})",
        "",
        f"Backup `{course.source.backup_name}`, Moodle {course.source.moodle_release or '?'}, "
        f"taken {date(course.source.backup_date)}. "
        + ("**Includes user data.**" if course.source.includes_users else "No user data."),
        "",
        "## Summary",
        "",
    ]
    by_type = Counter(a.modname for a in acts)
    lines += table(
        ["", "Count"],
        [
            ["Sections", len(course.outline)],
            ["Subsections", sum(1 for s in course.sections.values() if s.parent_cmid)],
            ["Activities", f"{len(course.activities)}: " + _counts(by_type)],
            [
                "Questions",
                f"{len(course.bank.entries)} bank entries ({course.bank.version_count} saved "
                f"versions): " + _counts(Counter(q.kind for q in questions)),
            ],
            ["Files", f"{len(course.files)} ({sum(not f.present for f in course.files)} missing)"],
            ["Links and embeds", _counts(Counter(r.kind for r in course.refs))],
        ],
    )
    lines += ["## Outline and target", ""]
    rows = []
    for section, item, parent in course.items():
        if parent is None and item is section.items[0]:
            rows.append([f"**{section.name}** (section)", "Section", STATUS["supported"]])
        act = item.activity
        m = map_activity(act)
        indent = "↳ " if parent else ""
        rows.append([f"{indent}{act.title} ({act.modname})", m.target, STATUS[m.status]])
    lines += table(["Moodle", "OpenLMS target", "Status"], rows)

    lines += ["## Activities: notes", ""]
    rows = []
    for act in acts:
        m = map_activity(act)
        if m.notes:
            rows.append([act.where, " ".join(m.notes)])
    lines += table(["Activity", "Notes"], rows) if rows else ["None.", ""]

    lines += ["## Quizzes", ""]
    for act in acts:
        if not isinstance(act.detail, QuizDetail):
            continue
        d = act.detail
        lines += [
            f"### {act.title}",
            "",
            f"Grade {d.grade:g}, {len(d.slots)} slot(s), attempts "
            f"{d.attempts or 'unlimited'}, time limit {d.time_limit_minutes or 'none'} min, "
            f"opens {date(d.opens) or '—'}, closes {date(d.closes) or '—'}.",
            "",
        ]
        fixed = Counter(s.question.kind for s in d.fixed_slots if s.question)
        if fixed:
            lines += [f"- Fixed questions: {_counts(fixed)}"]
        for g in d.random_groups:
            marks = ", ".join(f"{m:g}" for m in sorted(set(g.marks)))
            lines += [
                f"- Random: {g.count} from a pool of {len(g.pool)} (tags: "
                f"{', '.join(g.tags) or 'none'}; mark {marks})"
                + ("" if g.sufficient else " — **pool too small**")
            ]
        lines += [""]

    lines += ["## Question types", ""]
    kinds = Counter(q.kind for q in questions)
    lines += table(
        ["Type", "Count", "OpenLMS", "Status"],
        [
            [k, n, QTYPES.get(k, QTYPE_GAP)[0], STATUS[QTYPES.get(k, QTYPE_GAP)[1]]]
            for k, n in kinds.items()
        ],
    )

    lines += ["## Gradebook", ""]
    weights = course.gradebook.weights()
    rows = [
        [
            course.activities[i.cmid].where if i.cmid in course.activities else i.name,
            i.grade_type,
            f"{i.grade_max:g}",
            f"{i.grade_pass:g}" if i.grade_pass else "",
            f"{weights[i.cmid]:.0%}" if i.cmid in weights else "",
        ]
        for i in course.gradebook.items
    ]
    lines += [f"Aggregation: {course.gradebook.aggregation}.", ""]
    lines += table(["Item", "Type", "Max", "Pass", "Weight"], rows)

    lines += ["## External hosts", ""]
    hosts = Counter(_host(r.url) for r in course.refs if r.kind == "external")
    lines += (
        table(["Host", "Links"], [[h, n] for h, n in sorted(hosts.items())])
        if hosts
        else ["None.", ""]
    )
    lines += ["## Gaps and manual follow-ups", ""]
    rows = gaps(course)
    lines += table(["Where", "Status", "Detail"], rows) if rows else ["None.", ""]
    return "\n".join(lines)


def gaps(course: Course) -> list[list[str]]:
    rows = []
    for act in course.activities.values():
        m = map_activity(act)
        if m.status in (PARTIAL, GAP):
            rows.append([act.where, STATUS[m.status], " ".join(m.notes) or m.target])
    for kind, n in Counter(q.kind for q in course.bank.latest_questions()).items():
        target, status, note = QTYPES.get(kind, QTYPE_GAP)
        if status in (PARTIAL, GAP):
            rows.append([f"{n} question(s) of type {kind}", STATUS[status], f"→ {target}. {note}"])
    for ref in course.refs:
        if ref.kind == "pluginfile" and not ref.present:
            detail = f"Embedded file '{ref.file}' is not in the backup."
            rows.append([ref.location, STATUS[GAP], detail])
        elif ref.kind == "moodle_link":
            detail = "Link to another Moodle item: re-link it."
            rows.append([ref.location, STATUS[PARTIAL], detail])
        elif ref.kind in ("inline_script", "javascript") or ref.tag in EMBEDS:
            detail = f"Embedded {ref.tag or ref.kind}: review it."
            rows.append([ref.location, STATUS[PARTIAL], detail])
        elif ref.kind == "relative":
            detail = "Relative link won't resolve on OpenLMS."
            rows.append([ref.location, STATUS[PARTIAL], detail])
    return rows


def _counts(counter: Counter) -> str:
    return ", ".join(f"{n} {k}" for k, n in counter.most_common()) or "none"


def _host(url: str) -> str:
    return urlsplit(url if not url.startswith("//") else "https:" + url).hostname or url
