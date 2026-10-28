"""Read the question bank (``questions.xml``) and resolve quiz slots against it.

Since Moodle 4.0 a question lives in a *bank entry* with one or more *versions*.
``questions.xml`` lists every version, so counting ``<question>`` elements counts versions,
not questions. Quizzes point at bank entries, either directly (a fixed slot, optionally
pinned to one version) or through a filter (a random slot).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from ..safe.xml import html, integer, leaves, number, parse, text
from .model import Answer, BankEntry, Category, Question, QuestionBank, Version

# core\output\datafilter join types.
JOIN_NONE, JOIN_ANY, JOIN_ALL = 0, 1, 2
# Question types a random slot never picks.
NOT_RANDOMISABLE = {"description", "random"}


def read_bank(path: Path) -> QuestionBank:
    bank = QuestionBank()
    if not path.is_file():
        return bank
    for cat in parse(path).findall("question_category"):
        cat_id = int(cat.get("id"))
        context_id = integer(cat, "contextid")
        bank.categories[cat_id] = Category(
            cat_id, text(cat, "name") or "", context_id, integer(cat, "parent")
        )
        for entry in cat.findall("question_bank_entries/question_bank_entry"):
            entry_id = int(entry.get("id"))
            versions = [
                Version(
                    integer(v, "version") or 1,
                    text(v, "status") or "ready",
                    _question(q, entry_id, cat_id, context_id, bank.tag_names),
                )
                for v in entry.findall("question_version/question_versions")
                if (q := v.find("questions/question")) is not None
            ]
            bank.entries[entry_id] = BankEntry(entry_id, cat_id, versions)
    return bank


def _question(
    q: Element, entry_id: int, category_id: int, context_id: int | None, tags: dict[int, str]
) -> Question:
    qtype = text(q, "qtype") or ""
    tag_els = q.findall("tags/tag")
    for tag in tag_els:
        tags[int(tag.get("id"))] = text(tag, "rawname") or text(tag, "name") or ""
    plugin = q.find(f"plugin_qtype_{qtype}_question")
    answers, options = [], {}
    if plugin is not None:
        answers = [
            Answer(
                int(a.get("id")),
                html(a, "answertext"),
                number(a, "fraction") or 0.0,
                html(a, "feedback"),
            )
            for a in plugin.findall("answers/answer")
        ]
        # Type-specific settings: <multichoice><single>1</single>…</multichoice>,
        # <essay>…</essay>, … One level only; nested lists (match pairs) are not needed yet.
        for child in plugin:
            if child.tag != "answers" and not any(len(g) for g in child):
                options.update(leaves(child))
            elif child.tag != "answers":
                for item in child:
                    options.update({k: v for k, v in leaves(item).items() if k not in options})
    return Question(
        id=int(q.get("id")),
        entry_id=entry_id,
        category_id=category_id,
        context_id=context_id,
        name=text(q, "name") or "",
        qtype=qtype,
        text_html=html(q, "questiontext"),
        general_feedback_html=html(q, "generalfeedback"),
        default_mark=number(q, "defaultmark") or 0.0,
        tags=[text(t, "rawname") or text(t, "name") or "" for t in tag_els],
        tag_ids=[int(t.get("id")) for t in tag_els],
        answers=answers,
        options=options,
    )


def descendants(bank: QuestionBank, category_id: int) -> set[int]:
    found = {category_id}
    while True:
        children = {c.id for c in bank.categories.values() if c.parent in found} - found
        if not children:
            return found
        found |= children


def random_pool(bank: QuestionBank, condition: dict[str, Any]) -> tuple[list[Question], list[str]]:
    """The questions a random slot can draw, and the names of filters not applied.

    Mirrors Moodle 5: the category and tag filters are combined with the top-level join type;
    each filter has its own join type (none / any / all).
    """
    candidates = {
        e.id: q
        for e in bank.entries.values()
        if (q := e.latest) and q.qtype not in NOT_RANDOMISABLE
    }
    matched: list[set[int]] = []
    unhandled: list[str] = []
    for name, spec in condition.get("filter", {}).items():
        values = [v for v in spec.get("values", []) if v not in ("", None)]
        join = spec.get("jointype", JOIN_ANY)
        if name == "category":
            ids = {int(v) for v in values}
            if (spec.get("filteroptions") or {}).get("includesubcategories"):
                ids = set().union(*(descendants(bank, i) for i in ids)) if ids else set()
            inside = {e for e in candidates if bank.entries[e].category_id in ids}
            matched.append(set(candidates) - inside if join == JOIN_NONE else inside)
        elif name == "qtagids":
            if not values:
                continue
            wanted = {int(v) for v in values}

            def ok(q: Question, wanted: set[int] = wanted, join: int = join) -> bool:
                tags = set(q.tag_ids)
                if join == JOIN_ALL:
                    return wanted <= tags
                if join == JOIN_NONE:
                    return not wanted & tags
                return bool(wanted & tags)

            matched.append({e for e, q in candidates.items() if ok(q)})
        elif values:
            unhandled.append(name)

    if not matched:
        pool = set(candidates)
    elif condition.get("jointype", JOIN_ALL) == JOIN_ANY:
        pool = set().union(*matched)
    elif condition.get("jointype", JOIN_ALL) == JOIN_NONE:
        pool = set(candidates) - set().union(*matched)
    else:
        pool = set.intersection(*matched)
    return [candidates[e] for e in sorted(pool)], unhandled


def filter_key(condition: dict[str, Any]) -> str:
    """Stable key for "slots that draw from the same pool" (UI-only fields ignored)."""
    relevant = {
        name: {k: spec.get(k) for k in ("values", "jointype", "filteroptions")}
        for name, spec in condition.get("filter", {}).items()
    }
    return json.dumps({"filter": relevant, "jointype": condition.get("jointype")}, sort_keys=True)


def filter_tags(bank: QuestionBank, condition: dict[str, Any]) -> list[str]:
    values = (condition.get("filter", {}).get("qtagids") or {}).get("values", [])
    return [bank.tag_names.get(int(v), str(v)) for v in values if v not in ("", None)]
