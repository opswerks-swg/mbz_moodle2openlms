"""Moodle access restrictions ("availability" JSON) as a ``Restriction`` with a readable summary."""

from __future__ import annotations

import json
from typing import Any

from ..safe.xml import from_ts
from .model import Restriction

COMPLETION_STATES = {
    0: "is not complete",
    1: "is complete",
    2: "is complete and passed",
    3: "is complete and failed",
}


def parse(raw: str | None, names: dict[int, str]) -> Restriction | None:
    """None when nothing is restricted."""
    if not raw:
        return None
    tree = json.loads(raw)
    if not tree.get("c"):
        return None
    return Restriction(tree, describe(tree, names))


def describe(node: dict[str, Any], names: dict[int, str]) -> str:
    if "c" in node:
        op = node.get("op", "&")
        parts = [describe(child, names) for child in node["c"]]
        joined = (" AND " if op in ("&", "!|") else " OR ").join(parts)
        if len(parts) > 1:
            joined = f"({joined})"
        return f"NOT {joined}" if op.startswith("!") else joined
    kind = node.get("type")
    if kind == "completion":
        cm = node.get("cm")
        target = "the previous activity" if cm == -1 else f"'{names.get(cm, f'activity {cm}')}'"
        return f"{target} {COMPLETION_STATES.get(node.get('e'), 'has completion state ?')}"
    if kind == "date":
        when = from_ts(node.get("t"))
        stamp = when.isoformat(timespec="minutes") if when else "?"
        return f"from {stamp}" if node.get("d") == ">=" else f"until {stamp}"
    if kind == "grade":
        bounds = [f">= {node['min']}%" for _ in [0] if "min" in node]
        bounds += [f"< {node['max']}%" for _ in [0] if "max" in node]
        return f"grade item {node.get('id')} {' and '.join(bounds) or 'has a grade'}"
    if kind in ("group", "grouping"):
        return f"member of {kind} {node.get('id', '(any)')}"
    if kind == "profile":
        field = node.get("sf") or node.get("cf")
        return f"user profile '{field}' {node.get('op')} '{node.get('v', '')}'"
    return f"{kind} condition {json.dumps(node, sort_keys=True)}"
