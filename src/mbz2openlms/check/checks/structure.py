"""Sections, subsections and units: is every Moodle item in OpenLMS, and nothing extra?"""

from __future__ import annotations

from ...moodle.model import Activity, OutlineItem
from ...openlms.model import Section, Subsection
from ..context import Context, Node
from ..findings import FAIL, PASS, WARN
from ..text import COVERAGE, found, norm
from .gaps import HANDLED


def run(ctx: Context) -> None:
    course = ctx.openlms
    by_name = {norm(s.name): s for s in course.sections}
    expected = [s for s in ctx.moodle.outline if any(_learner(i) for i in s.items)]
    order = []
    for outline in expected:
        section = by_name.get(norm(outline.name))
        where = f"section '{outline.name}'"
        if section is None:
            ctx.add(f"section|{outline.name}", "structure", where, FAIL, "section not in OpenLMS")
            for _s, item, _parent in ctx.moodle.items():
                if _s is outline and _learner(item):
                    act = item.activity
                    detail = f"not found: section '{outline.name}' is missing"
                    ctx.add(f"activity|{act.where}", "structure", act.where, FAIL, detail)
            continue
        order.append(course.sections.index(section))
        ctx.add(f"section|{outline.name}", "structure", where, PASS, "present")
        _summary(ctx, outline.section.summary_html, outline.name, section)
        for item in outline.items:
            _place(ctx, item, section, None)
            for child in item.children:
                _place(ctx, child, section, item.activity.title)
    if order != sorted(order):
        ctx.add("section-order", "structure", "course", WARN, "sections are in a different order")
    names = {norm(s.name) for s in expected}
    for section in course.sections:
        if norm(section.name) not in names:
            where = f"section '{section.name}'"
            detail = "section is not in the Moodle course"
            ctx.add(f"extra-section|{section.name}", "structure", where, FAIL, detail)


def extras(ctx: Context) -> None:
    """Units and subsections nothing in Moodle accounts for. Runs after the content checks,
    which claim book chapters and overview units."""
    for section, sub, unit in ctx.openlms.units():
        if id(unit) in ctx.used_units:
            continue
        if norm(unit.name) == "Overview" and all(
            c.tag == "html" for c in unit.xml if isinstance(c.tag, str)
        ):
            continue  # a section or subsection summary, checked as content
        where = f"{section.name} › {sub.name} › {unit.name}"
        ctx.add(f"extra-unit|{where}", "structure", where, FAIL, "unit is not in the Moodle course")
    for section, sub in ctx.openlms.subsections():
        if not sub.units and id(sub) not in ctx.used_subs:
            where = f"{section.name} › {sub.name}"
            ctx.add(f"extra-subsection|{where}", "structure", where, WARN, "empty subsection")


def published(ctx: Context) -> None:
    """Studio API only: the checked OLX is Studio's draft; learners see what is published."""
    for section, sub, unit in ctx.openlms.units():
        where = f"{section.name} › {sub.name} › {unit.name}"
        if unit.published is False:
            ctx.add(f"unpublished|{where}", "structure", where, FAIL, "never published")
        elif unit.has_changes:
            detail = "unpublished changes: learners see the previous version; publish it"
            ctx.add(f"unpublished|{where}", "structure", where, WARN, detail)


def _learner(item: OutlineItem) -> bool:
    """Learner-facing and of a type OpenLMS has (other types are reported as gaps)."""
    return item.activity.modname in HANDLED | {"subsection"}


def _summary(ctx: Context, html: str, name: str, section: Section) -> None:
    if not html.strip():
        return
    cov = found(html, [u.xml for s in section.subsections for u in s.units])
    status = PASS if cov >= COVERAGE else WARN
    where = f"section '{name}' summary"
    ctx.add(f"summary|{name}", "content", where, status, f"{cov:.0%} of the summary found")


def _place(ctx: Context, item: OutlineItem, section: Section, moodle_sub: str | None) -> None:
    act = item.activity
    if not _learner(item):
        return
    node = _find(ctx, section, act, moodle_sub)
    if node is None:
        detail = f"not found in OpenLMS section '{section.name}'"
        ctx.add(f"activity|{act.where}", "structure", act.where, FAIL, detail)
        return
    ctx.nodes[act.cmid] = node
    ctx.add(f"activity|{act.where}", "structure", act.where, PASS, f"at {node.where}")
    if not act.visible:
        detail = "hidden in Moodle: check it is hidden (or removed) in OpenLMS"
        ctx.add(f"hidden|{act.where}", "structure", act.where, WARN, detail)


def _find(ctx: Context, section: Section, act: Activity, moodle_sub: str | None) -> Node | None:
    title = norm(act.title)
    subs = [s for s in section.subsections if norm(s.name) == title]
    if act.modname == "subsection":
        return _take_sub(ctx, section, subs)
    if act.modname == "book":
        # A subsection named after the book, or the one holding its first chapter.
        if node := _take_sub(ctx, section, subs):
            return node
        chapters = [norm(c.title) for c in act.detail.chapters if not c.hidden]
        for s in section.subsections:
            if chapters and any(norm(u.name) == chapters[0] for u in s.units):
                return Node(section, s, None)
        return None
    units = [(s, u) for s in section.subsections for u in s.units if norm(u.name) == title]
    preferred = [(s, u) for s, u in units if norm(s.name) in {title, norm(moodle_sub)}]
    for s, u in preferred + units:
        if id(u) not in ctx.used_units:
            ctx.used_units.add(id(u))
            if norm(s.name) == title:
                ctx.used_subs.add(id(s))
            return Node(section, s, u)
    return _take_sub(ctx, section, subs)


def _take_sub(ctx: Context, section: Section, subs: list[Subsection]) -> Node | None:
    for s in subs:
        if id(s) not in ctx.used_subs:
            ctx.used_subs.add(id(s))
            return Node(section, s, None)
    return None
