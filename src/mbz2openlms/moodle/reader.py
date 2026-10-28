"""Read an extracted Moodle course backup into a ``Course``."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

from ..htmlutil import links, pluginfile_name
from ..safe.archive import opened
from ..safe.xml import flag, html, integer, number, parse, text, timestamp
from . import activities, availability
from .model import (
    Activity,
    ContentRef,
    Course,
    File,
    Gradebook,
    GradeItem,
    OutlineItem,
    OutlineSection,
    QuestionBank,
    Section,
    Source,
)
from .questions import read_bank

# Moodle grade aggregation codes (grade/lib.php).
AGGREGATIONS = {
    0: "mean",
    2: "median",
    4: "lowest",
    6: "highest",
    8: "mode",
    10: "weighted mean",
    11: "simple weighted mean",
    12: "mean with extra credits",
    13: "natural",
}
COMPLETION = {0: "none", 1: "manual", 2: "automatic"}
GRADE_TYPES = {0: "none", 1: "value", 2: "scale", 3: "text"}


@contextlib.contextmanager
def open_backup(source: Path) -> Iterator[Path]:
    """Yield the extracted backup directory of a .mbz file (or an extracted directory)."""
    with opened(source, "moodle_backup.xml", "Moodle course backup (.mbz)") as root:
        yield root


def read_backup(source: Path) -> Course:
    """Read a .mbz file or an extracted backup directory.

    File contents stay on disk, so a ``Course`` read from a .mbz file can't be used to copy
    files once this returns; use ``open_backup`` + ``read_course`` for that.
    """
    with open_backup(source) as root:
        return read_course(root, source.name)


def read_course(root: Path, name: str | None = None) -> Course:
    return _Reader(root, name).read()


class _Reader:
    def __init__(self, root: Path, name: str | None) -> None:
        self.root = root
        self.backup = parse(root / "moodle_backup.xml")
        self.info = self.backup.find("information")
        self.name = name or text(self.info, "name") or root.name
        self.bank: QuestionBank = read_bank(root / "questions.xml")
        self.files = self._files()
        self.refs: list[ContentRef] = []

    def read(self) -> Course:
        course_el = self._optional("course/course.xml")
        acts = self._activities()
        names = {a.cmid: a.title for a in acts.values()}
        for act, raw in zip(acts.values(), self._raw_restrictions, strict=True):
            act.restriction = availability.parse(raw, names)
        sections = self._sections(names)
        summary = html(course_el, "summary")
        self._scan(summary, "course summary", self._course_context, None)
        self._scan_questions()
        self._resolve_files()
        return Course(
            source=Source(
                backup_name=self.name,
                moodle_release=text(self.info, "moodle_release"),
                backup_date=timestamp(self.info, "backup_date"),
                wwwroot=text(self.info, "original_wwwroot"),
                course_id=integer(self.info, "original_course_id"),
                includes_users=self._setting("users") == "1",
            ),
            fullname=text(self.info, "original_course_fullname") or "",
            shortname=text(self.info, "original_course_shortname") or "",
            start=timestamp(self.info, "original_course_startdate"),
            summary_html=summary,
            sections=sections,
            activities=acts,
            outline=self._outline(sections, acts),
            bank=self.bank,
            gradebook=self._gradebook(acts),
            files=self.files,
            refs=self.refs,
        )

    @property
    def _course_context(self) -> int | None:
        return integer(self.info, "original_course_contextid")

    def _optional(self, rel: str):
        path = self.root / rel
        return parse(path) if path.is_file() else None

    def _setting(self, name: str) -> str | None:
        for setting in self.backup.findall("information/settings/setting"):
            if text(setting, "level") == "root" and text(setting, "name") == name:
                return text(setting, "value")
        return None

    # -- structure ----------------------------------------------------------------------

    def _activities(self) -> dict[int, Activity]:
        acts: dict[int, Activity] = {}
        self._raw_restrictions: list[str | None] = []
        for entry in self.backup.findall("information/contents/activities/activity"):
            cmid = integer(entry, "moduleid") or 0
            modname = text(entry, "modulename") or ""
            title = text(entry, "title") or ""
            folder = self.root / (text(entry, "directory") or "")
            module = parse(folder / "module.xml")
            act_xml = folder / f"{modname}.xml"
            context_id = None
            if act_xml.is_file():
                act_el = parse(act_xml)
                context_id = int(act_el.get("contextid")) if act_el.get("contextid") else None
                detail, fields = activities.read(modname, act_el.find(modname), self.bank)
            else:
                detail, fields = activities.read(modname, module, self.bank)
            for label, content in fields:
                self._scan(content, f"{modname} '{title}' {label}", context_id, cmid)
            acts[cmid] = Activity(
                cmid=cmid,
                modname=modname,
                title=title,
                section_id=integer(entry, "sectionid") or 0,
                context_id=context_id,
                visible=flag(module, "visible"),
                completion=COMPLETION.get(integer(module, "completion") or 0, "unknown"),
                restriction=None,
                detail=detail,
            )
            self._raw_restrictions.append(text(module, "availability"))
        return acts

    def _sections(self, names: dict[int, str]) -> dict[int, Section]:
        sections = {}
        for entry in self.backup.findall("information/contents/sections/section"):
            el = parse(self.root / (text(entry, "directory") or "") / "section.xml")
            section = Section(
                id=integer(entry, "sectionid") or 0,
                number=integer(el, "number") or 0,
                name=text(el, "name") or text(entry, "title") or "",
                summary_html=html(el, "summary"),
                visible=flag(el, "visible"),
                restriction=availability.parse(text(el, "availabilityjson"), names),
                parent_cmid=integer(entry, "parentcmid"),
                sequence=[int(c) for c in (text(el, "sequence") or "").split(",") if c.strip()],
            )
            self._scan(
                section.summary_html,
                f"section '{section.name}' summary",
                self._course_context,
                None,
            )
            sections[section.id] = section
        return sections

    def _outline(
        self, sections: dict[int, Section], acts: dict[int, Activity]
    ) -> list[OutlineSection]:
        """Sections by number; items in each section's sequence order (not by number)."""
        delegated = {s.parent_cmid: s for s in sections.values() if s.parent_cmid}

        def items(section: Section) -> list[OutlineItem]:
            out = []
            for cmid in section.sequence:
                if cmid not in acts:
                    continue
                item = OutlineItem(acts[cmid])
                if child := delegated.get(cmid):
                    item.section = child
                    item.children = items(child)
                out.append(item)
            return out

        top = sorted((s for s in sections.values() if not s.parent_cmid), key=lambda s: s.number)
        return [OutlineSection(s, items(s)) for s in top]

    # -- question bank, grades, files ----------------------------------------------------

    def _scan_questions(self) -> None:
        for q in self.bank.latest_questions():
            where = f"question '{q.name}' (entry {q.entry_id})"
            self._scan(q.text_html, where, q.context_id, None)
            self._scan(q.general_feedback_html, f"{where} feedback", q.context_id, None)
            for a in q.answers:
                self._scan(a.text_html, f"{where} answer", q.context_id, None)
                self._scan(a.feedback_html, f"{where} answer feedback", q.context_id, None)

    def _gradebook(self, acts: dict[int, Activity]) -> Gradebook:
        gb = self._optional("gradebook.xml")
        aggregation = "natural"
        course_item = None
        items: list[GradeItem] = []
        if gb is not None:
            cats = gb.findall("grade_categories/grade_category")
            top = next((c for c in cats if integer(c, "parent") is None), cats[0] if cats else None)
            if top is not None:
                aggregation = AGGREGATIONS.get(integer(top, "aggregation") or 13, "unknown")
            for el in gb.findall("grade_items/grade_item"):
                item = _grade_item(el, None)
                if item.item_type == "course":
                    course_item = item
                elif item.item_type == "manual":
                    items.append(item)
        for act in acts.values():
            grades = self._optional(f"activities/{act.modname}_{act.cmid}/grades.xml")
            if grades is not None:
                found = grades.findall("grade_items/grade_item")
                items += [_grade_item(el, act.cmid) for el in found]
        return Gradebook(aggregation, items, course_item)

    def _files(self) -> list[File]:
        xml = self._optional("files.xml")
        if xml is None:
            return []
        files = []
        for f in xml.findall("file"):
            name = text(f, "filename")
            if name in (None, "."):  # directory rows
                continue
            digest = text(f, "contenthash") or ""
            path = self.root / "files" / digest[:2] / digest
            files.append(
                File(
                    id=int(f.get("id")),
                    context_id=integer(f, "contextid"),
                    component=text(f, "component"),
                    filearea=text(f, "filearea"),
                    filepath=text(f, "filepath") or "/",
                    filename=name,
                    size=integer(f, "filesize") or 0,
                    mimetype=text(f, "mimetype"),
                    content_hash=digest,
                    path=path,
                    present=path.is_file(),
                )
            )
        return files

    def _resolve_files(self) -> None:
        """Match each @@PLUGINFILE@@ reference to a file in the same context."""
        for ref in self.refs:
            if ref.kind != "pluginfile":
                continue
            ref.file = pluginfile_name(ref.url)
            base = ref.file.rsplit("/", 1)[-1]
            matches = [
                f for f in self.files if f.context_id == ref.context_id and f.filename == base
            ]
            ref.present = bool(matches) and all(m.present for m in matches)

    def _scan(self, html_: str, location: str, context_id: int | None, cmid: int | None) -> None:
        for link in links(html_):
            self.refs.append(ContentRef(link.kind, link.tag, link.url, location, context_id, cmid))


def _grade_item(el, cmid: int | None) -> GradeItem:
    return GradeItem(
        id=int(el.get("id")),
        item_type=text(el, "itemtype") or "",
        module=text(el, "itemmodule"),
        cmid=cmid,
        name=text(el, "itemname"),
        category_id=integer(el, "categoryid"),
        grade_type=GRADE_TYPES.get(integer(el, "gradetype") or 0, "unknown"),
        grade_max=number(el, "grademax") or 0.0,
        grade_pass=number(el, "gradepass") or 0.0,
        weight_raw=number(el, "aggregationcoef2") or 0.0,
        weight_override=flag(el, "weightoverride"),
        hidden=flag(el, "hidden"),
    )
