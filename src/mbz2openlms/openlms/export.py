"""Read a migrated course from a Studio export (Tools › Export) or any OLX course folder.

An export has no subsection prerequisites (Open edX keeps them in the milestones tables), so
``prereqs_known`` is False and the checker reports prerequisites as "not checked".
"""

from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from ..safe.archive import ArchiveError, opened
from ..safe.xml import parse_olx
from .model import MigratedCourse, MigratedError, Section, Subsection, Unit


def from_export(source: Path) -> MigratedCourse:
    """Read an export ``.tar.gz`` or an extracted course folder."""
    try:
        with opened(source, "course.xml", "Studio course export (.tar.gz)") as root:
            return read_olx(root, f"Studio export `{source.name}`")
    except ArchiveError as exc:
        raise MigratedError(str(exc)) from exc


def read_olx(root: Path, source: str) -> MigratedCourse:
    pointer = _parse(root / "course.xml")
    run = pointer.get("url_name") or ""
    course = _load(root, "course", run)
    sections = []
    for ch in course.findall("chapter"):
        section = Section(ch.get("url_name") or "", ch.get("display_name") or "")
        for seq in ch.findall("sequential"):
            sub = Subsection(
                id=seq.get("url_name") or "",
                name=seq.get("display_name") or "",
                graded=seq.get("graded") == "true",
                format=seq.get("format"),
                start=seq.get("start"),
                due=seq.get("due"),
                time_limited=seq.get("is_time_limited") == "true",
            )
            sub.units = [
                Unit(v.get("url_name") or "", v.get("display_name") or "", v)
                for v in seq.findall("vertical")
            ]
            section.subsections.append(sub)
        sections.append(section)

    graders: dict[str, float] = {}
    cutoff = None
    policy = root / "policies" / run / "grading_policy.json"
    if policy.is_file():
        data = json.loads(policy.read_text(encoding="utf-8"))
        graders = {g["type"]: float(g["weight"]) for g in data.get("GRADER", [])}
        cutoff = (data.get("GRADE_CUTOFFS") or {}).get("Pass")
    static = root / "static"
    files = {p.relative_to(static).as_posix() for p in static.rglob("*") if p.is_file()}
    key = f"course-v1:{pointer.get('org')}+{pointer.get('course')}+{run}"
    return MigratedCourse(source, key, sections, graders, cutoff, False, files)


def _load(root: Path, block_type: str, url_name: str) -> etree._Element:
    """``<type>/<url_name>.xml`` with every pointer child replaced by its content."""
    el = _parse(root / block_type / f"{url_name}.xml")
    if not el.get("url_name"):
        el.set("url_name", url_name)
    if el.tag == "html" and el.get("filename") and not len(el):
        html = root / "html" / f"{el.get('filename')}.html"
        if html.is_file():
            el.text = html.read_text(encoding="utf-8")
    _inline(root, el)
    return el


def _inline(root: Path, el: etree._Element) -> None:
    for i, child in enumerate(list(el)):
        if not isinstance(child.tag, str):
            continue
        url_name = child.get("url_name")
        if url_name and not len(child) and (root / child.tag / f"{url_name}.xml").is_file():
            loaded = _load(root, child.tag, url_name)
            loaded.tail = child.tail
            el[i] = loaded
        else:
            _inline(root, child)


def _parse(path: Path) -> etree._Element:
    try:
        return parse_olx(path)
    except (OSError, etree.XMLSyntaxError) as exc:
        raise MigratedError(f"Cannot read {path.name}: {exc}") from exc
