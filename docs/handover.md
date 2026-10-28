# Handover to the instructors

What is handed over:

- **The runbook**, [runbook.md](runbook.md). It is the only document an instructor needs to
  migrate a course.
- **The checker**, `mbz2openlms check`, described in [checker.md](checker.md).

## Status

| Acceptance criterion | Status | Evidence |
|---|---|---|
| The route is chosen and the comparison with the alternatives is documented | ✅ measured on course 131 · ⏳ review | [route-decision.md](route-decision.md) |
| The sample course is migrated to preprod by following the runbook, with no steps beyond those it lists | ⏳ | Preprod run log below |
| The checker passes on the migrated sample, reports differences, and the known gaps are documented | ✅ local tutor (API and export) · ⏳ preprod | `known-gaps/a11-fnd-lnx01.toml`, [inventory-and-mapping.md](inventory-and-mapping.md) |
| Automated tests for the checker pass, including a run on the sample course | ✅ | `uv run pytest` with `M2O_SAMPLE_MBZ` set; CI runs the rest |
| The runbook is written and reviewed | ✅ written · ⏳ reviewed | |
| An instructor migrates a course using only the runbook and runs the checker | ⏳ | Handover check below |
| Bay and Geo have reviewed and accepted the result | ⏳ | Sign-off below |

## Walkthrough: one migration (about 60 minutes)

Run it with the instructor driving and the maintainer watching. The instructor shares their
screen and reads the runbook aloud. The maintainer doesn't touch the keyboard and only notes
where the runbook was unclear.

1. **Setup (10 min).** Runbook step 0: clone the repository, `uv sync`,
   `uv run mbz2openlms --version`. Show the two files that steer the checker:
   `review-rules.toml` and `known-gaps/`.
2. **Backup (5 min).** Runbook step 1 on the chosen course. Point out "Include enrolled users"
   and the `-nu.mbz` name.
3. **Convert (5 min).** Runbook step 2. Open `conversion-report.md` together and read the
   follow-up list. Open `inventory.md` and find a known gap in it.
4. **Studio (20 min).** Runbook steps 3 to 6: create the course, import it, and do every
   follow-up. Do one prerequisite together, then the instructor does the rest alone. Publish and
   export.
5. **Check (10 min).** Runbook step 7. Read the report section by section. Go through the
   prerequisite checklist in Studio. Run `gaps init` if the course is new and explain the review.
6. **Break it (5 min).** In Studio, change one quiz answer and publish. Export, check, and see
   the failure. Undo the change, export, check, and see it pass.
7. **Wrap up (5 min).** Runbook step 8: what to send to whom, and what never to share (the
   `.tar.gz`, `inventory.json`, the `.mbz`).

## Handover check (acceptance)

An instructor migrates a course **other than Linux Fundamentals**, chosen from the Course
Inventory, using only the runbook:

- [ ] No help beyond the runbook was needed. If it was, note the step, fix the runbook, and
      repeat with the next course.
- [ ] `mbz2openlms check` says PASS on the export.
- [ ] Every "Not checked" prerequisite was ticked off in Studio.
- [ ] The course's known-gaps file was created with `gaps init` and sent to Bay and Geo.
- [ ] Time taken: ______

## Sign-off (Bay and Geo)

- [ ] Route decision accepted ([route-decision.md](route-decision.md)).
- [ ] Known gaps for Linux Fundamentals accepted: `known-gaps/a11-fnd-lnx01.toml`, "Reviewed
      by" filled in.
- [ ] Wording that replaces the lab password line in "Before you begin" decided.
- [ ] Review rules: the OpenLMS course review-rules document delivered and encoded in
      `review-rules.toml` (allowed hosts: KodeKloud, GitHub, Linode, or replacements).
- [ ] Learner data stays out of scope (Bay).
- [ ] Platform: timed exams on or off (decides whether time limits stay known gaps).
- [ ] Runbook reviewed.

## Preprod run log (sample course)

| Date | Who | Course key | Steps beyond the runbook | Check result |
|---|---|---|---|---|
| ⏳ | | | | |
