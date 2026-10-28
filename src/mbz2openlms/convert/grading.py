"""Grading policy and course policy from the Moodle gradebook."""

from __future__ import annotations

from .build import INFO, MANUAL, Build


def build_policies(b: Build) -> None:
    weights = dict(b.weights)
    if weights and any(w is None for w in weights.values()):
        b.note(
            MANUAL,
            "grading",
            "Some weights could not be read from the Moodle gradebook: graded types are weighted "
            "equally. Check Studio › Settings › Grading.",
        )
        weights = {k: 1 / len(weights) for k in weights}
    total = sum(w for w in weights.values() if w is not None)
    if weights and abs(total - 1) > 0.001:
        b.note(INFO, "grading", f"Weights summed to {total:.0%}; scaled to 100%.")
        weights = {k: (w or 0) / total for k, w in weights.items()} if total else weights
    weights.update(b.fixed_weights)
    graders = [
        {"type": t, "short_label": t[:12], "min_count": 1, "drop_count": 0, "weight": round(w, 4)}
        for t, w in weights.items()
    ]
    ratios = sorted({round(r, 4) for r in b.pass_ratios})
    course_item = b.course.gradebook.course_item
    if course_item and course_item.grade_pass and course_item.grade_max:
        ratios = [round(course_item.grade_pass / course_item.grade_max, 4)]
    if len(ratios) == 1:
        cutoff = ratios[0]
    else:
        cutoff = 0.5
        if ratios:
            b.note(
                MANUAL,
                "grading",
                f"Moodle pass marks differ ({', '.join(f'{r:.0%}' for r in ratios)}): the course "
                "pass cutoff is set to 50%. Choose one in Studio › Settings › Grading.",
            )
    b.olx.grading_policy = {"GRADER": graders, "GRADE_CUTOFFS": {"Pass": cutoff}}
    types = {c.block_type for c in b.olx.components()}
    policy = {
        "display_name": b.olx.display_name,
        "advanced_modules": sorted(types & {"openassessment", "survey"}),
    }
    if b.olx.start:
        policy["start"] = b.olx.start
    if b.gating:
        policy["enable_subsection_gating"] = True
    b.olx.policy = policy
