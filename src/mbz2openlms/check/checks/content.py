"""Text of pages, labels, book chapters, links, intros, and Feedback activities."""

from __future__ import annotations

import json

from lxml import etree

from ...moodle.model import (
    Activity,
    BookDetail,
    FeedbackDetail,
    FeedbackItem,
    PageDetail,
    UrlDetail,
)
from ..context import Context, Node
from ..findings import FAIL, PASS, WARN
from ..text import COVERAGE, expected_words, found, norm

# Checked by their own modules, or without content of their own.
OWN_CHECKS = {"assign", "quiz", "subsection", "qbank"}


def run(ctx: Context) -> None:
    for cmid, node in ctx.nodes.items():
        act = ctx.moodle.activities[cmid]
        d = act.detail
        if isinstance(d, BookDetail):
            _book(ctx, act, d, node)
        elif isinstance(d, PageDetail) and act.modname == "page":
            text(ctx, f"text|{act.where}", act.where, d.content_html, node.elements)
        elif act.modname == "label":
            text(ctx, f"text|{act.where}", act.where, d.intro_html, node.elements)
        elif isinstance(d, UrlDetail):
            _link(ctx, act, d, node)
        elif isinstance(d, FeedbackDetail):
            _feedback(ctx, act, d, node)
        if act.modname not in OWN_CHECKS | {"label", "feedback"} and expected_words(d.intro_html):
            text(ctx, f"intro|{act.where}", act.where, d.intro_html, node.elements, WARN, "intro")
        if act.modname == "subsection":
            # The summary goes to the first subsection of the split: look in the whole section.
            summary = next(
                (s.summary_html for s in ctx.moodle.sections.values() if s.parent_cmid == cmid),
                "",
            )
            roots = [u.xml for sub in node.section.subsections for u in sub.units]
            text(ctx, f"summary|{act.where}", act.where, summary, roots, WARN, "summary")


def text(
    ctx: Context,
    fid: str,
    where: str,
    html: str | None,
    roots: list[etree._Element],
    status: str = FAIL,
    what: str = "text",
) -> None:
    if not expected_words(html):
        return
    cov = found(html, roots)
    ok = cov >= COVERAGE
    ctx.add(fid, "content", where, PASS if ok else status, f"{cov:.0%} of the {what} found")


def _book(ctx: Context, act: Activity, d: BookDetail, node: Node) -> None:
    units = {norm(u.name): u for u in node.sub.units}
    for ch in d.chapters:
        if ch.hidden:
            continue
        where = f"{act.where} chapter '{ch.title}'"
        unit = units.get(norm(ch.title))
        if unit is None:
            ctx.add(f"chapter|{where}", "structure", where, FAIL, "no unit for the chapter")
            continue
        ctx.used_units.add(id(unit))
        text(ctx, f"text|{where}", where, ch.content_html, [unit.xml])


def _link(ctx: Context, act: Activity, d: UrlDetail, node: Node) -> None:
    url = d.external_url
    present = bool(url) and any(
        url in etree.tostring(r, encoding="unicode", method="xml") or url in " ".join(r.itertext())
        for r in node.elements
    )
    detail = "link present" if present else "the URL is not in the unit"
    ctx.add(f"link|{act.where}", "content", act.where, PASS if present else FAIL, detail)


def _feedback(ctx: Context, act: Activity, d: FeedbackDetail, node: Node) -> None:
    agree = [i for i in d.questions if i.is_agreement]
    rated = [i for i in d.questions if i.is_rating]
    if d.is_agreement:
        _agreement(ctx, act, agree, node)
    elif rated:
        labels = set()
        for survey in node.find("survey"):
            for _key, q in json.loads(survey.get("questions") or "[]"):
                labels.add(norm(" ".join(expected_words(q.get("label")))))
        missing = [i for i in rated if norm(" ".join(expected_words(i.name))) not in labels]
        ctx.add(
            f"survey|{act.where}",
            "content",
            act.where,
            FAIL if missing else PASS,
            f"{len(rated) - len(missing)} of {len(rated)} rating question(s) in a survey",
        )
    text(ctx, f"intro|{act.where}", act.where, d.intro_html, node.elements, WARN, "intro")


def _agreement(ctx: Context, act: Activity, items: list[FeedbackItem], node: Node) -> None:
    for problem in node.find("problem"):
        choices = problem.findall(".//checkboxgroup/choice")
        if len(choices) != len(items):
            continue
        texts = [norm(" ".join(c.itertext())) for c in choices]
        missing = [i for i in items if not any(norm(i.name) in t for t in texts)]
        issues = [f"{len(missing)} statement(s) not found"] if missing else []
        if not all(c.get("correct") == "true" for c in choices):
            issues.append("not every box is required")
        ctx.add(
            f"agreement|{act.where}",
            "content",
            act.where,
            FAIL if issues else PASS,
            "; ".join(issues) or f"checkbox problem with all {len(items)} statements",
        )
        return
    detail = f"no checkbox problem with {len(items)} statement(s)"
    ctx.add(f"agreement|{act.where}", "content", act.where, FAIL, detail)
