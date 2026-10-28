"""The Markdown docs render as intended: no raw tags outside code.

A placeholder such as <A> outside backticks is read as an HTML tag and turns the rest of the
page into a link.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"<(?!https?://)[A-Za-z/][^>]*>")


def test_no_raw_tags_outside_code():
    found = []
    for path in [ROOT / "README.md", ROOT / "CLAUDE.md", *(ROOT / "docs").glob("*.md")]:
        in_code = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("```"):
                in_code = not in_code
            elif not in_code and TAG.search(re.sub(r"`[^`]*`", "", line)):
                found.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()}")
    assert not found, "\n".join(found)
