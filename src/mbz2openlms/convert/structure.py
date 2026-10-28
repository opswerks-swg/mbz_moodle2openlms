"""Moodle structure to Open edX structure.

Moodle section          -> section (chapter)
Moodle subsection       -> one or more subsections, split wherever an activity is gated on
                           completing an earlier one in it: Open edX gates whole subsections
                           (prerequisites), not single units
top-level activity      -> its own subsection (consecutive pages/labels/URLs/files share one)
activity                -> one unit (a book gives one unit per chapter)
"""

from __future__ import annotations

from ..moodle.model import Activity, OutlineItem, OutlineSection
from ..olx.model import Section, Subsection, Unit
from ..safe.xml import from_ts
from .build import DROPPED, INFO, MANUAL, Build, Units, olx_date
from .handlers import HANDLERS, SIMPLE, SKIPPED


def build_sections(b: Build) -> None:
    for outline in b.course.outline:
        section = Section(b.olx.url_name("chapter", outline.section.id), outline.name)
        if outline.section.summary_html.strip():
            section.subsections.append(_overview(b, outline))
        _items(b, outline, section)
        if section.subsections:
            b.olx.sections.append(section)
        else:
            b.note(INFO, f"section '{outline.name}'", "Empty after conversion: not created.")


def _overview(b: Build, outline: OutlineSection) -> Subsection:
    where = f"section '{outline.name}' summary"
    html = b.html("Overview", outline.section.summary_html, _course_context(b), where)
    url = b.olx.url_name("overview", outline.section.id)
    return Subsection(url, "Overview", [Unit(b.olx.url_name(url, "unit"), "Overview", [html])])


def _items(b: Build, outline: OutlineSection, section: Section) -> None:
    simple: list[Activity] = []

    def add(sub: Subsection) -> None:
        if sub.units:
            section.subsections.append(sub)

    def flush() -> None:
        if simple:
            add(_subsection(b, section, simple[0].title, list(simple)))
            simple.clear()

    for item in outline.items:
        act = item.activity
        if act.modname in SIMPLE:
            simple.append(act)
            continue
        flush()
        if act.modname == "subsection":
            for sub in _moodle_subsection(b, section, item):
                add(sub)
        elif act.modname not in SKIPPED:
            add(_subsection(b, section, act.title, [act]))
    flush()


def _moodle_subsection(b: Build, section: Section, item: OutlineItem) -> list[Subsection]:
    acts = [c.activity for c in item.children if c.activity.modname not in SKIPPED]
    groups: list[list[Activity]] = [[]]
    for act in acts:
        deps = set(act.restriction.completion_cmids()) if act.restriction else set()
        if groups[-1] and deps & {a.cmid for a in groups[-1]}:
            groups.append([])
        groups[-1].append(act)
    groups = [g for g in groups if g]
    if not groups:
        b.note(INFO, item.activity.where, "Empty: not created.")
        return []
    subsections, named = [], False
    for i, group in enumerate(groups):
        main = any(a.modname in ("quiz", "assign") for a in group)
        if len(groups) == 1 or (main and not named):
            name, named = item.activity.title, True
        else:
            name = group[0].title
        summary = item.section.summary_html if item.section and i == 0 else ""
        subsections.append(_subsection(b, section, name, group, summary))
    return subsections


def _subsection(
    b: Build, section: Section, name: str, acts: list[Activity], summary: str = ""
) -> Subsection:
    sub = Subsection(b.olx.url_name("seq", acts[0].cmid), name)
    if summary.strip():
        html = b.html("Overview", summary, _course_context(b), f"subsection '{name}' summary")
        sub.units.append(Unit(b.olx.url_name(sub.url_name, "overview"), "Overview", [html]))
    for act in acts:
        units = _convert(b, act)
        if units:
            sub.units += units.units
            sub.attrs.update(units.attrs)
    b.place(acts, section.display_name, sub)
    _restrictions(b, acts, sub)
    return sub


def _convert(b: Build, act: Activity) -> Units | None:
    handler = HANDLERS.get(act.modname)
    if handler is None:
        detail = f"'{act.modname}' activities are not converted: rebuild it by hand."
        b.note(MANUAL, act.where, detail)
        return None
    if not act.visible:
        b.note(MANUAL, act.where, "Hidden in Moodle: hide it in Studio or delete it.")
    return handler(act, b)


def _restrictions(b: Build, acts: list[Activity], sub: Subsection) -> None:
    prereqs: set[str] = set()
    for act in acts:
        r = act.restriction
        if r is None:
            continue
        if not r.flat:
            b.note(MANUAL, act.where, f"Restriction not converted: {r.summary}.")
            continue
        for cmid in r.completion_cmids():
            target = b.placed_in.get(cmid)
            if target and target != sub.display_name:
                prereqs.add(target)
            elif target is None and cmid in b.course.activities:
                prereqs.add(b.course.activities[cmid].title)
        for kind, ts in r.dates():
            when = from_ts(ts)
            b.record_date(act.where, f"available {kind}", when)
            if kind == "from" and b.opts.keep_dates and when:
                start = olx_date(when)
                if start > sub.attrs.get("start", ""):
                    sub.attrs["start"] = start
            elif kind == "until":
                b.note(
                    DROPPED,
                    act.where,
                    "'Until' date has no per-activity equivalent: use the subsection due date.",
                )
        for kind in r.other_types():
            b.note(MANUAL, act.where, f"'{kind}' restriction not converted: {r.summary}.")
    if len(prereqs) == 1:
        b.gating = True
        b.note(
            MANUAL,
            f"subsection '{sub.display_name}'",
            f"Set prerequisite '{prereqs.pop()}' with minimum score 100% (Studio › subsection › "
            "Configure › Access). Moodle required it to be completed first.",
        )
    elif prereqs:
        b.note(
            MANUAL,
            f"subsection '{sub.display_name}'",
            "Moodle required completing "
            + ", ".join(f"'{p}'" for p in sorted(prereqs))
            + ". OpenLMS allows one prerequisite per subsection: choose one or leave it open.",
        )


def _course_context(b: Build) -> int | None:
    # Section summaries live in the course context; files there are matched by name.
    for ref in b.course.refs:
        if ref.location.startswith("section '") or ref.location == "course summary":
            return ref.context_id
    return None
