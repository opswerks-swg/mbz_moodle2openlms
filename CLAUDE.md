# CLAUDE.md

Guidance for working on this repository.

## What this is

`mbz2openlms`: a CLI that converts Moodle course backups (`.mbz`) into OpenLMS (Open edX, Ulmo)
course archives, and checks a migrated course against its backup. Instructors use it through
`docs/runbook.md`. The route decision is in `docs/route-decision.md`.

## Commands

```bash
uv sync
uv run pytest                                   # all tests (synthetic backup + fake Studio)
uv run pytest tests/test_check.py -k mutation   # a subset
M2O_SAMPLE_MBZ=<course 131 .mbz> uv run pytest  # adds the real-course tests
uv run ruff check . && uv run ruff format --check .   # line length 100
```

## Layout

The pipeline: `safe` → `moodle` (read) → `convert` + `olx` (build) | `openlms` + `check` (verify).

- `safe/`: untrusted input. `archive.py` extracts tar/zip and rejects traversal and links.
  `xml.py` parses backup XML with defusedxml (and maps `$@NULL@$` to None) and OLX with lxml,
  with entities and network off.
- `moodle/`: a typed model of the backup (`model.py`). `reader.py` builds it.
  `activities/` has one reader per module type. `questions.py` handles the Moodle 4+ question
  bank: bank **entries** with **versions**, and quizzes reference entries through fixed slots
  (optionally pinned to a version) or random slots (category/tag filters). Count entries, not
  `<question>` elements. `availability.py` parses access restrictions.
- `mapping.py`: the feature table (Moodle → OpenLMS, supported/partial/gap).
- `convert/`: `structure.py` maps sections and subsections. It splits a Moodle subsection
  wherever an activity is gated on an earlier one, because Open edX gates whole subsections.
  `handlers/` holds one function per module type. `problems.py` and `ora.py` build components.
  `grading.py` builds the policies. Everything not carried over becomes a `Note` in
  `conversion-report.md`.
- `olx/`: the OLX model and writer (Studio export layout) and `pack`.
- `openlms/`: reads the migrated course into one model. `export.py` reads a Studio export or
  OLX folder, which has no prerequisites. `studio.py` reads the REST APIs (`course_index`,
  `course_grading`, `olx-export` per unit) and turns Ulmo asset URLs back into `/static/`.
- `check/`: `checks/` holds one module per area (structure first, since it places each activity;
  then content, quizzes, assignments, gaps, grading, prerequisites, dates, files, rules).
  `known_gaps.py`, `review.py` (the rules from `review-rules.toml`), `text.py` (coverage and
  answer comparison).
- `report/`: Markdown and JSON reports.
- `e2e/`: the end-to-end harness against a running Studio. `local.py` is for the tutor dev
  only, through docker exec.
- `credentials.py`, `htmlutil.py`: neutral helpers shared by both sides.

## Invariants (tested in `tests/test_invariants.py`)

- **`check/` and `openlms/` never import `convert/` or `olx/`**, so a converter bug can't mask
  itself. `moodle/` imports neither side.
- **No answer keys or credentials in shareable output** (`*.md`, `check.json`). Answer text is
  only in `inventory.json`, `olx/` and the `.tar.gz`. Tests use `SECRET_ANSWER` and `CREDENTIAL`
  from `tests/fixtures/mbz_builder.py`.
- Finding ids are stable (`kind|where`). Known-gaps files depend on them: don't change a format
  without migrating `known-gaps/*.toml`.
- lxml elements: track them in sets by element, never by `id()`. Proxies are short-lived and
  their ids get reused.

## Tests

- `tests/fixtures/mbz_builder.py` builds a synthetic Moodle 5 backup with the edge cases (see
  its docstring).
- `test_check.py`: a faithful conversion must give exactly `BASELINE`. Each entry in
  `MUTATIONS` breaks one thing and must give exactly the expected finding. Add a mutation with
  every new check.
- `fake_studio.py` serves a course through the APIs the checker and `e2e` use, including the
  Ulmo asset URLs.
- `test_sample_course.py` is opt-in (`M2O_SAMPLE_MBZ`): the real pilot course, as converted,
  after the runbook's follow-ups, and through `e2e`.

## Never

- Point `e2e` at a real course, or at prod. `e2e run` replaces the course's
  content.
- Commit `.mbz`, `.imscc`, `out/`, or course exports.
