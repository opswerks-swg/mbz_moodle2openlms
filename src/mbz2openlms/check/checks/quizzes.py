"""Quiz questions: text, answers, marks, attempts; random pools; essays."""

from __future__ import annotations

from lxml import etree

from ...mapping import CONVERTED_QTYPES
from ...moodle.model import Activity, Question, QuizDetail, RandomGroup, Slot
from ..context import Context, Node
from ..findings import FAIL, PASS, WARN
from ..text import (
    COVERAGE,
    answer_counts,
    coverage,
    expected_words,
    moodle_answers,
    problem_answers,
    rubric_points,
    words_of,
)
from .content import text


def run(ctx: Context) -> None:
    for cmid, node in ctx.nodes.items():
        act = ctx.moodle.activities[cmid]
        if isinstance(act.detail, QuizDetail):
            _quiz(ctx, act, act.detail, node)


def _quiz(ctx: Context, act: Activity, d: QuizDetail, node: Node) -> None:
    for slot in d.fixed_slots:
        q = slot.question
        if q is None:
            continue
        where = f"{act.where} slot {slot.number} '{q.name}'"
        if q.qtype == "description":
            text(ctx, f"text|{where}", where, q.text_html, node.elements)
        elif q.qtype == "essay":
            _essay(ctx, q, slot, node, where)
        elif q.kind in CONVERTED_QTYPES:
            _question(ctx, q, node.find("problem"), slot.max_mark, where, d)
    for n, group in enumerate(d.random_groups, 1):
        _bank(ctx, act, d, group, n, node)
    if d.intro_html.strip():
        text(ctx, f"intro|{act.where}", act.where, d.intro_html, node.elements, WARN, "intro")


def _essay(ctx: Context, q: Question, slot: Slot, node: Node, where: str) -> None:
    expected = expected_words(q.text_html)
    scored = [(coverage(expected, words_of([o])), o) for o in node.find("openassessment")]
    cov, ora = max(scored, default=(0.0, None), key=lambda pair: pair[0])
    if ora is None or cov < COVERAGE:
        ctx.add(f"essay|{where}", "quizzes", where, FAIL, "no ORA with the essay prompt")
        return
    points = rubric_points(ora)
    ok = abs(points - slot.max_mark) < 0.01
    detail = f"ORA found; rubric out of {points:g}, Moodle mark {slot.max_mark:g}"
    ctx.add(f"essay|{where}", "quizzes", where, PASS if ok else WARN, detail)


def _bank(ctx: Context, act: Activity, d: QuizDetail, group: RandomGroup, n: int, node: Node):
    where = f"{act.where} random group {n}"
    banks = [
        b
        for b in node.find("itembank") + node.find("library_content")
        if b.get("max_count") == str(group.count)
    ]
    bank = max(banks, default=None, key=lambda b: _overlap(group.pool, b.findall(".//problem")))
    if bank is None:
        detail = f"no problem bank showing {group.count} problem(s)"
        ctx.add(f"bank|{where}", "quizzes", where, FAIL, detail)
        return
    problems = bank.findall(".//problem")
    ok = len(problems) == len(group.pool)
    ctx.add(
        f"bank|{where}",
        "quizzes",
        where,
        PASS if ok else FAIL,
        f"'{bank.get('display_name')}' shows {group.count} of {len(problems)} "
        f"(Moodle: {group.count} of {len(group.pool)})",
    )
    mark = group.marks[0] if group.marks else None
    for q in group.pool:
        _question(ctx, q, problems, mark, f"{where} '{q.name}' (question {q.id})", d)


def _question(
    ctx: Context,
    q: Question,
    problems: list[etree._Element],
    mark: float | None,
    where: str,
    quiz: QuizDetail,
) -> None:
    if q.kind not in CONVERTED_QTYPES:
        return  # reported as a gap
    question_words = expected_words(q.text_html)
    scored = sorted(
        (
            (coverage(question_words, words_of([p])), i, p)
            for i, p in enumerate(problems)
            if p not in ctx.used_problems
        ),
        key=lambda t: (-t[0], t[1]),
    )
    candidates = [p for cov, _, p in scored if cov >= COVERAGE]
    if not candidates:
        ctx.add(f"question|{where}", "quizzes", where, FAIL, "question text not found")
        return
    expected = moodle_answers(q)
    problem = next((p for p in candidates if problem_answers(p) == expected), candidates[0])
    ctx.used_problems.add(problem)
    actual = problem_answers(problem)
    issues = []
    if actual != expected:
        issues.append(
            f"answers differ: Moodle {answer_counts(expected)}, OpenLMS {answer_counts(actual)}"
        )
    weight = problem.get("weight")
    if mark is not None and weight is not None and abs(float(weight) - mark) > 0.001:
        issues.append(f"weight {weight}, Moodle mark {mark:g}")
    if quiz.attempts and problem.get("max_attempts") != str(quiz.attempts):
        issues.append(f"max attempts {problem.get('max_attempts')}, Moodle {quiz.attempts}")
    ctx.add(
        f"question|{where}",
        "quizzes",
        where,
        FAIL if issues else PASS,
        "; ".join(issues) or f"found; {answer_counts(expected)} match",
    )


def _overlap(pool: list[Question], problems: list[etree._Element]) -> int:
    texts = [words_of([p]) for p in problems]
    return sum(
        any(coverage(expected_words(q.text_html), t) >= COVERAGE for t in texts) for q in pool
    )
