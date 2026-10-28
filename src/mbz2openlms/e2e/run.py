"""``mbz2openlms e2e run``: drive the runbook on a test course and check the checker.

1. Import the converted archive (replaces the test course's content).
2. Check: the runbook's follow-ups (prerequisites) must be reported missing.
3. Apply the follow-ups as an instructor would in Studio (prerequisites at 100%, due dates in
   the future, credentials scrubbed), through the API, or pause while a person does them.
4. Check: must pass.
5. Break the course in known ways (a changed answer, draft then published; a prerequisite
   below 100%; a past due date): each must be caught. Then put it back.
6. Optionally export the course (local tutor only) and check the export.

Every change goes through Studio's REST APIs with the checker's OAuth client.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from lxml import etree
from lxml import html as lxml_html

from .. import credentials
from ..check import FAIL, PASS, SKIP, WARN, KnownGap, Report, Rules, check
from ..htmlutil import plain_text
from ..moodle.model import Course
from ..openlms.export import from_export
from ..openlms.model import MigratedCourse, MigratedError
from ..openlms.studio import StudioClient, from_studio
from ..report.check import write

FOLLOW_UP_CHECKS = {"prerequisites", "dates"}
PAST = "2020-01-01T00:00:00+00:00"
PLACEHOLDER = "[credential removed: ask the course team]"


@dataclass
class Step:
    name: str
    ok: bool
    detail: str


@dataclass
class E2E:
    client: StudioClient
    course_key: str
    moodle: Course
    known_gaps: list[KnownGap]
    rules: Rules
    out: Path
    due: datetime
    allow_fail: set[str] = field(default_factory=set)
    log: Callable[[str], None] = print
    pause: Callable[[str], None] | None = None  # set: wait for a person instead of the API
    sleep: Callable[[float], None] = time.sleep
    steps: list[Step] = field(default_factory=list)
    _n: int = 0
    _course: MigratedCourse | None = None

    def step(self, name: str, ok: bool, detail: str) -> bool:
        self.steps.append(Step(name, ok, detail))
        self.log(f"{'✅' if ok else '❌'} {name}: {detail}")
        return ok

    @property
    def passed(self) -> bool:
        return all(s.ok for s in self.steps)

    def run(self, archive: Path, breaks: bool = True, export: Callable[[Path], Path] | None = None):
        if not self._import(archive):
            return False
        self._reset_prereqs()
        before = self.check("before-follow-ups")
        expected = [f for f in before.findings if f.fix and f.check == "prerequisites"]
        missed = [f for f in expected if f.status != FAIL]
        self.step(
            "Checker catches the missing follow-ups",
            not missed,
            f"{len(expected) - len(missed)} of {len(expected)} prerequisite(s) reported missing"
            if expected
            else "the Moodle course has no prerequisites to follow up",
        )
        self._follow_ups(before)
        after = self.check("after-follow-ups")
        if not self._clean(after, "Migrated course passes after the follow-ups"):
            return False
        if breaks:
            for name, mutation in (
                ("changed answer", self._break_answer),
                ("prerequisite below 100%", self._break_min_score),
                ("due date in the past", self._break_due),
            ):
                try:
                    mutation()
                except MigratedError as exc:
                    self.step(f"Break: {name}", False, str(exc))
            self._clean(self.check("after-reverting"), "Course is back to passing")
        if export:
            self._export(export, after)
        return self.passed

    def check(self, stem: str) -> Report:
        self._n += 1
        self._course = from_studio(self.client, self.course_key)
        report = check(self.moodle, self._course, self.known_gaps, self.rules)
        path = write(report, self.out, f"{self._n}-{stem}")
        counts = ", ".join(
            f"{n} {s}" for s in (FAIL, WARN, "known gap", SKIP, PASS) if (n := report.count(s))
        )
        self.log(f"   check ({stem}): {counts} → {path}")
        return report

    def _clean(self, report: Report, name: str) -> bool:
        fails = {f.id for f in report.findings if f.status == FAIL} - self.allow_fail
        follow_ups = [
            f for f in report.findings if f.check in FOLLOW_UP_CHECKS and f.status in (FAIL, WARN)
        ]
        problems = sorted(fails) + [f"{f.id} ({f.status})" for f in follow_ups if f.id not in fails]
        allowed = {f.id for f in report.findings if f.status == FAIL} & self.allow_fail
        detail = "; ".join(problems) or "no failures"
        if allowed:
            detail += f" (+{len(allowed)} allowed by --allow-fail)"
        return self.step(name, not problems, detail)

    # -- import -------------------------------------------------------------------------

    def _import(self, archive: Path) -> bool:
        try:
            task = self.client.import_course(self.course_key, archive)
            state = ""
            for _ in range(300):
                state = self.client.import_state(self.course_key, task, archive.name)
                if state in ("Succeeded", "Failed", "Canceled"):
                    break
                self.sleep(2)
        except MigratedError as exc:
            return self.step("Import into Studio", False, str(exc))
        return self.step("Import into Studio", state == "Succeeded", f"import task {state}")

    def _reset_prereqs(self) -> None:
        """Clear prerequisites left by an earlier run: an import keeps them (they are not in
        OLX). The v0 xblock API rejects an empty prereqUsageKey, but turning "is prerequisite"
        off on the prerequisite subsection removes it and every requirement on it."""
        cleared = 0
        for sub in self._subsections():
            if sub.get("is_prereq"):
                self.client.patch_xblock(self.course_key, sub["id"], {"isPrereq": False})
                cleared += 1
        left = [s["display_name"] for s in self._subsections() if s.get("prereq")]
        if left:
            raise MigratedError(f"could not clear old prerequisites on {', '.join(left)}")
        if cleared:
            self.log(f"   cleared {cleared} prerequisite(s) left by an earlier run")

    def _subsections(self) -> list[dict[str, Any]]:
        index = self.client.get(f"/api/contentstore/v1/course_index/{self.course_key}")
        chapters = (index["course_structure"].get("child_info") or {}).get("children") or []
        return [s for ch in chapters for s in (ch.get("child_info") or {}).get("children") or []]

    # -- the runbook's follow-ups -------------------------------------------------------

    def _follow_ups(self, before: Report) -> None:
        todo = [
            f
            for f in before.findings
            if f.fix and f.check in FOLLOW_UP_CHECKS and f.status in (FAIL, WARN)
        ]
        secrets = [f for f in before.findings if f.id.startswith("review-secret|")]
        if self.pause:
            lines = [f"  - {f.where}: {f.detail}" for f in todo + secrets]
            self.pause(
                "Do these follow-ups in Studio (prerequisites at 100%, due dates in the future, "
                "credentials removed), publish, then press Enter:\n" + "\n".join(lines)
            )
            self.step("Follow-ups done in Studio", True, f"{len(todo) + len(secrets)} item(s)")
            return
        for f in todo:
            self._apply(f.fix, self.due.isoformat())
        scrubbed = self._scrub_credentials() if secrets else 0
        self.step(
            "Follow-ups applied through the API",
            True,
            f"{len(todo)} setting(s), {scrubbed} component(s) with credentials scrubbed",
        )

    def _apply(self, fix: dict[str, str], due: str, min_score: int = 100) -> None:
        if fix["action"] == "prereq":
            self.client.patch_xblock(self.course_key, fix["prereq"], {"isPrereq": True})
            payload = {
                "prereqUsageKey": fix["prereq"],
                "prereqMinScore": min_score,
                "prereqMinCompletion": 0,
            }
            self.client.patch_xblock(self.course_key, fix["subsection"], payload)
        elif fix["action"] == "due":
            payload: dict[str, Any] = {"metadata": {fix["field"]: due}}
            if fix["field"] != "due":  # a component setting: publish it, as Studio's Save does
                payload["publish"] = "make_public"
            self.client.patch_xblock(self.course_key, fix["block"], payload)

    def _scrub_credentials(self) -> int:
        """Replace credentials in HTML components with a placeholder, as the runbook asks."""
        done = 0
        for element, usage in self._course.block_ids.items():
            if element.tag != "html" or not credentials.find(plain_text(element.text or "")):
                continue
            data = scrub_html(self.client.get_xblock(self.course_key, usage).get("data") or "")
            self.client.patch_xblock(
                self.course_key, usage, {"data": data, "publish": "make_public"}
            )
            done += 1
        return done

    # -- break it on purpose ------------------------------------------------------------

    def _expect(self, name: str, report: Report, wanted: Callable[[Any], bool]) -> bool:
        hits = [f for f in report.findings if wanted(f)]
        detail = "; ".join(f"{f.status}: {f.where} — {f.detail}" for f in hits[:2])
        return self.step(f"Break: {name}", bool(hits), detail or "not reported")

    def _break_answer(self) -> None:
        problem, original = self._choice_problem()
        self.client.patch_xblock(self.course_key, problem, {"data": flip_answers(original)})
        try:
            self._expect(
                "changed answer, not published",
                self.check("break-answer-draft"),
                lambda f: f.id.startswith("unpublished|") and f.status == WARN,
            )
            self.client.patch_xblock(self.course_key, problem, {"publish": "make_public"})
            self._expect(
                "changed answer, published",
                self.check("break-answer-published"),
                lambda f: (
                    f.id.startswith("question|")
                    and f.status == FAIL
                    and "answers differ" in f.detail
                ),
            )
        finally:
            restore = {"data": original, "publish": "make_public"}
            self.client.patch_xblock(self.course_key, problem, restore)

    def _break_min_score(self) -> None:
        fix = self._first_fix("prereq")
        self._apply(fix, self.due.isoformat(), min_score=0)
        try:
            self._expect(
                "prerequisite below 100%",
                self.check("break-min-score"),
                lambda f: f.fix == fix and f.status == FAIL and "100%" in f.detail,
            )
        finally:
            self._apply(fix, self.due.isoformat())

    def _break_due(self) -> None:
        fix = self._first_fix("due", field_name="due")
        self._apply(fix, PAST)
        try:
            self._expect(
                "due date in the past",
                self.check("break-due"),
                lambda f: f.fix == fix and f.status == FAIL and "in the past" in f.detail,
            )
        finally:
            self._apply(fix, self.due.isoformat())

    def _first_fix(self, action: str, field_name: str | None = None) -> dict[str, str]:
        report = check(self.moodle, self._course, self.known_gaps, self.rules)
        for f in report.findings:
            if f.fix and f.fix["action"] == action:
                if field_name is None or f.fix.get("field") == field_name:
                    return f.fix
        raise MigratedError(f"no {action} in this course to break")

    def _choice_problem(self) -> tuple[str, str]:
        for element, usage in self._course.block_ids.items():
            if element.tag == "problem" and element.find(".//choice") is not None:
                data = self.client.get_xblock(self.course_key, usage).get("data") or ""
                if 'correct="true"' in data and 'correct="false"' in data:
                    return usage, data
        raise MigratedError("no multiple-choice problem to break")

    # -- the export path ----------------------------------------------------------------

    def _export(self, export: Callable[[Path], Path], after: Report) -> None:
        try:
            archive = export(self.out / "export.tar.gz")
        except (OSError, MigratedError) as exc:
            self.step("Studio export checks", False, f"export failed: {exc}")
            return
        report = check(self.moodle, from_export(archive), self.known_gaps, self.rules)
        write(report, self.out, f"{self._n + 1}-from-export")
        prereqs = [f for f in report.findings if f.id.startswith("prereq|")]
        new_fails = {f.id for f in report.findings if f.status == FAIL} - {
            f.id for f in after.findings if f.status == FAIL
        }
        ok = all(f.status == SKIP for f in prereqs) and not new_fails
        detail = f"{len(prereqs)} prerequisite check(s) not checked (as expected)"
        if new_fails:
            detail += "; failures the API run didn't have: " + ", ".join(sorted(new_fails))
        self.step("Studio export checks", ok, detail)


def default_due() -> datetime:
    return (datetime.now(UTC) + timedelta(days=30)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )


def scrub_html(html: str) -> str:
    """Replace each innermost block (paragraph, list item, cell, …) holding a credential with a
    placeholder, as an instructor would edit that line in Studio."""
    root = lxml_html.fragment_fromstring(html, create_parent="div")
    hits = credentials.blocks_with_credentials(root)
    for el in hits:
        tail = el.tail
        el.clear()
        el.text, el.tail = PLACEHOLDER, tail
    if not hits and credentials.find(root.text_content()):
        return credentials.redact(html)  # no block to replace: plain text
    out = etree.tostring(root, encoding="unicode", method="html")
    return out[len("<div>") : -len("</div>")]


def flip_answers(data: str) -> str:
    return re.sub(
        r'correct="(true|false)"',
        lambda m: 'correct="false"' if m.group(1) == "true" else 'correct="true"',
        data,
    )
