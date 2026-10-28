# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

CI (`.github/workflows/ci.yml`) runs `uv sync --locked`, ruff and pytest: commit `uv.lock` with
any dependency change.

The CLI (`cli.py`, click): `inventory`, `convert`, `check`, `gaps init`, `e2e local-setup`,
`e2e run`. `check` exits 0 PASS, 1 FAIL, 2 error. It reads a Studio export (`--export`) or the
Studio APIs (`--course`). API mode takes `M2O_STUDIO_URL`, `M2O_LMS_URL`, `M2O_CLIENT_ID`,
`M2O_CLIENT_SECRET` and optionally `M2O_CA_BUNDLE`.

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
- `convert/`: `build.py`'s `Build` is the state the handlers share (the OLX course, the notes,
  the static files, the grading inputs). `structure.py` maps sections and subsections. It
  splits a Moodle subsection wherever an activity is gated on an earlier one, because Open edX
  gates whole subsections. `handlers/` holds one function per module type. `problems.py` and
  `ora.py` build components. Their XML must be well-formed, so `xhtml.py` turns Moodle's loose
  HTML into XHTML first. `grading.py` builds the policies. Everything not carried over becomes
  a `Note` (manual, dropped or info) in `conversion-report.md`.
- `olx/`: the OLX model and writer (Studio export layout) and `pack`.
- `openlms/`: reads the migrated course into one model. `export.py` reads a Studio export or
  OLX folder, which has no prerequisites. `studio.py` reads the REST APIs (`course_index`,
  `course_grading`, `olx-export` per unit) and turns Ulmo asset URLs back into `/static/`.
- `check/`: `checks/` holds one module per area (structure first, since it places each activity;
  then content, quizzes, assignments, gaps, grading, prerequisites, dates, files, rules).
  `context.py` is the state they share: both courses, the findings, and the `Node` (unit or
  subsection) where structure placed each Moodle activity. `known_gaps.py`, `review.py` (the
  rules from `review-rules.toml`, provisional until the OpenLMS review-rules document arrives),
  `text.py` (coverage and answer comparison).
- `report/`: Markdown and JSON reports.
- `e2e/`: the end-to-end harness against a running Studio. `local.py` is for the tutor dev
  only, through docker exec.
- `credentials.py`, `htmlutil.py`: neutral helpers shared by both sides.
- `paths.py`: the repository root, from which `out/`, `review-rules.toml` and `known-gaps/` are
  resolved, never from the current folder. Instructors run an editable `uv tool install` from
  the clone (runbook step 0) and call `mbz2openlms` from anywhere. `M2O_HOME` replaces the
  root; `tests/conftest.py` sets it for every test, so tests never write into the clone.

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
- `Rules.load()` never returns empty rules: a missing `review-rules.toml` is an error (exit 2),
  since with no rules blocked components would pass (`tests/test_cli.py`).

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
- `test_docs.py` fails on a raw tag outside code in `README.md`, `CLAUDE.md` and `docs/*.md`.
  Put placeholders such as `<course>` in backticks or a code block.

## Never

- Point `e2e` at a real course, or at prod. `e2e run` replaces the course's
  content.
- Commit `.mbz`, `.imscc`, `out/`, or course exports.
