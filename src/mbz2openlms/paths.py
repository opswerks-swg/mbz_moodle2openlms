"""Where the repository's files are: review rules, known gaps and the output folder.

The tool runs from a clone (``uv tool install --editable <clone>``), so these are in the clone
wherever the command is run from. ``M2O_HOME`` replaces the clone (tests use it).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class SetupError(Exception):
    """The tool can't find the repository it should run from."""


def root() -> Path:
    home = os.environ.get("M2O_HOME")
    if home:
        return Path(home).expanduser().resolve()
    if not (REPO / "pyproject.toml").is_file():
        raise SetupError(
            "mbz2openlms isn't running from its repository. Install it from the clone with "
            "uv tool install --editable, as in docs/runbook.md step 0."
        )
    return REPO


def out() -> Path:
    return root() / "out"


def rules_file() -> Path:
    return root() / "review-rules.toml"


def gaps_dir() -> Path:
    return root() / "known-gaps"


def display(path: Path) -> str:
    """``path`` relative to the repository when it is inside it, so reports don't show a home
    folder."""
    try:
        return str(path.resolve().relative_to(root()))
    except (ValueError, SetupError):
        return str(path)
