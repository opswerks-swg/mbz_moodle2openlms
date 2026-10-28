"""Invariants: the checker never imports the converter, and shareable reports never contain
answer keys or credentials."""

from __future__ import annotations

import ast
from pathlib import Path

from mbz2openlms.check import check
from mbz2openlms.convert import convert
from mbz2openlms.openlms.export import read_olx
from mbz2openlms.report import check as check_report
from mbz2openlms.report import conversion, inventory, to_json
from tests.fixtures.mbz_builder import CREDENTIAL, SECRET_ANSWER

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "mbz2openlms"
BUILD_SIDE = {"convert", "olx"}


def _imports(path: Path) -> set[str]:
    """Package-relative modules imported by ``path``, e.g. {"convert.build", "moodle.model"}."""
    module = path.relative_to(PACKAGE).with_suffix("").parts
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(module[: len(module) - node.level])
                found.add(".".join(base + ([node.module] if node.module else [])))
            elif node.module and node.module.startswith("mbz2openlms"):
                found.add(node.module.removeprefix("mbz2openlms").lstrip("."))
        elif isinstance(node, ast.Import):
            found |= {a.name.removeprefix("mbz2openlms.") for a in node.names}
    return found


def test_check_side_never_imports_the_converter():
    for folder in ("check", "openlms"):
        for path in (PACKAGE / folder).rglob("*.py"):
            bad = {m for m in _imports(path) if m.split(".")[0] in BUILD_SIDE}
            assert not bad, f"{path.relative_to(PACKAGE)} imports {bad}"


def test_moodle_reader_imports_neither_side():
    for path in (PACKAGE / "moodle").rglob("*.py"):
        bad = {m for m in _imports(path) if m.split(".")[0] in BUILD_SIDE | {"check"}}
        assert not bad, f"{path.relative_to(PACKAGE)} imports {bad}"


def test_shareable_reports_have_no_answer_keys(course, olx_copy):
    result = convert(course)
    report = check(course, read_olx(olx_copy, "t"))
    shareable = {
        "inventory.md": inventory.render(course),
        "conversion-report.md": conversion.render(course, result, "x.tar.gz"),
        "check-report.md": check_report.render(report),
    }
    for name, text in shareable.items():
        assert SECRET_ANSWER not in text, name
        assert CREDENTIAL not in text, name
    # The internal JSON does have them: the test would pass vacuously otherwise.
    assert SECRET_ANSWER in to_json(course)


def test_check_json_has_no_answer_keys(course, olx_copy, tmp_path):
    report = check(course, read_olx(olx_copy, "t"))
    check_report.write(report, tmp_path)
    text = (tmp_path / "check.json").read_text()
    assert SECRET_ANSWER not in text
    assert CREDENTIAL not in text
