# Sample output

What `mbz2openlms` writes to `out/<course>/`, so you know what to expect before running it. These
are the shareable reports only. The other outputs (`inventory.json`, `olx/`, the `.tar.gz`,
`check.json`) hold answer keys and are never committed.

The course is **Synthetic Linux (SYN-LNX 01)**, the made-up course the tests use
(`tests/fixtures/mbz_builder.py`). It is not a real course. It is small but has the awkward cases:
a quiz gated on an agreement, random questions, a question type with no equivalent, a forum, a
missing image, a credential in a page, due dates.

| File | Written by | What it tells you |
|---|---|---|
| [inventory.md](inventory.md) | `inventory`, `convert` | What is in the Moodle backup and where each part goes in OpenLMS: supported, partial or gap |
| [conversion-report.md](conversion-report.md) | `convert` | What was built, where each activity went, and the **manual follow-ups to do in Studio** (runbook step 5) |
| [check-report.md](check-report.md) | `check` | **FAIL**: the course straight out of `convert`, before the follow-ups |
| [check-report-after-follow-ups.md](check-report-after-follow-ups.md) | `check` | **PASS**: the same course after the follow-ups |

## From FAIL to PASS

`check-report.md` checks the archive straight out of `convert`, as if runbook steps 5 and 6 were
skipped. Each line that isn't a pass, and the step that clears it:

| Line in `check-report.md` | Cleared by | In the PASS report |
|---|---|---|
| ❌ Moodle link left over: `@@PLUGINFILE@@/gone.png` | 5d: upload the missing file and fix the link | gone |
| ❌ possible password or key assignment | 5c: remove the credential from the page | gone |
| ⚠️ no due date set for the new run | 5b: set the new run's due dates | gone |
| ⚠️ external host not yet reviewed | Nothing yet: waits on the review-rules document | still there: read it |
| 📝 Known gap | Nothing: accepted in `known-gaps/<course>.toml` (`gaps init`, step 7) | still there |
| ⏸ subsection 'Final' should require 'Agreement' | 5a, then the step 7 checklist | still there: tick it off by hand |

## Regenerating

The reports change when their format does. To rebuild them, from the repository root (the
`Generated` timestamp in the check reports will differ):

```bash
H=$(mktemp -d) B=$(mktemp -d)/backup-moodle2-course-syn-lnx-01
touch "$H/pyproject.toml" && cp review-rules.toml "$H/"
uv run python -c "import sys; sys.path.insert(0, '.')
from pathlib import Path; from tests.fixtures.mbz_builder import sample_backup
sample_backup(Path(sys.argv[1]))" "$B"
export M2O_HOME="$H"   # keeps the run out of the clone's out/ and known-gaps/
uv run mbz2openlms convert "$B"
uv run mbz2openlms gaps init "$B"
uv run mbz2openlms check "$B" --export "$H/out/syn-lnx-01/syn-lnx_01-2026.tar.gz"   # FAIL, exit 1
cp "$H"/out/syn-lnx-01/{inventory,conversion-report,check-report}.md docs/samples/
```

Then the PASS report: do the follow-ups on a copy of the OLX, as `tests/test_check.py` does, and
check that copy.

```bash
O="$H/olx-after-follow-ups" && cp -R "$H/out/syn-lnx-01/olx" "$O" && C="$O/course"
sed -i.bak -e 's#<img src="@@PLUGINFILE@@/gone.png">##' \
  -e 's#Lab login password: [^<]*#Ask your instructor for the lab password.#' \
  "$C/html/html_Welcome.html"
for s in 13 19 20; do
  sed -i.bak 's#graded="true"#graded="true" due="2027-01-01T00:00:00Z"#' "$C/sequential/seq_$s.xml"
done
sed -i.bak 's#<openassessment #<openassessment submission_due="2027-01-01T00:00:00Z" #' \
  "$C/vertical/unit_13.xml"
find "$C" -name '*.bak' -delete
uv run mbz2openlms check "$B" --export "$O" -o "$H/after"
cp "$H/after/check-report.md" docs/samples/check-report-after-follow-ups.md
```
