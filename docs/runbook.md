# Runbook: migrate a course from Moodle to OpenLMS

For instructors. Follow it top to bottom for one course. It takes about an hour for a course the
size of Linux Fundamentals, most of it spent on the Studio follow-ups in step 5.

The route is fixed (see [route-decision.md](route-decision.md)): take a Moodle backup, convert it
with `mbz2openlms`, import the result in Studio, finish the listed follow-ups by hand, then check
the result with `mbz2openlms check`. Learner data (enrolments, attempts, grades, submissions)
is **not** migrated.

> Prod is out of scope for now: migrate into **preprod** only, until Bay and Geo sign off.

## 0. Before you start

You need:

| What | How to check |
|---|---|
| Teacher (or manager) access to the course in Moodle | You can see **More › Course reuse** on the course page. |
| A Studio account on OpenLMS preprod with permission to create courses, or a course already created for you in which you have the **Staff** or **Admin** role | You can open <https://openlms-studio.werkslearning-preprod.opswerks.com> and see **New course** or the course. |
| This repository and `uv` on your machine | `uv --version` prints a version. Install: <https://docs.astral.sh/uv/>. |
| The tool installed | In the repository folder: `uv sync`, then `uv run mbz2openlms --version`. |

All commands below run from the repository folder.

Two files in the repository decide what the checker accepts:

- `review-rules.toml`: the OpenLMS course review rules (allowed external hosts, forbidden
  component types). Don't edit it during a migration.
- `known-gaps/<course>.toml`: the differences between Moodle and OpenLMS that were reviewed and
  accepted for that course. Step 7 explains how to create one for a new course.

## 1. Back up the course in Moodle

1. Open the course in Moodle. Note the URL's `id=` number (course 131 for Linux Fundamentals).
2. Go to **More › Course reuse › Backup**.
3. On **Initial settings**, **untick "Include enrolled users"** (learner data stays in Moodle).
   Leave the other defaults on, in particular activities, blocks, question bank, and files.
4. **Next** through **Schema settings** (keep every section and activity ticked) to
   **Confirmation and review**, then **Perform backup**, then **Continue**.
5. On the **Restore** page, under **Course backup area**, click **Download** next to the new file.
   Its name ends in `-nu.mbz` ("no users").

Keep the `.mbz` out of the repository and out of chat tools: it holds the course content and
the quiz answer keys.

## 2. Convert the backup

```bash
uv run mbz2openlms convert ~/Downloads/backup-moodle2-course-131-....mbz
```

It prints the archive it wrote and how many manual follow-ups there are. Everything is in
`out/<course>/` (for example `out/a11-fnd-lnx01/`):

| File | What it is | Share it? |
|---|---|---|
| `<course>-<run>.tar.gz` | The course to import in Studio | No: it holds the answer keys |
| `conversion-report.md` | Where each activity went, the **manual follow-ups**, what was not carried over, and the old run's dates | Yes, within the team |
| `inventory.md` | What is in the Moodle course and how each item maps | Yes, within the team |
| `inventory.json`, `olx/` | Full detail, for troubleshooting | No: they hold the answer keys |

Options you may need: `--run 2027` (the run part of the course key, default `2026`),
`--number` (the course number, default the Moodle short name). Leave `--keep-dates` and
`--timed-exams` off unless the platform team has said otherwise.

**Open `conversion-report.md` now.** Its "Manual follow-up in Studio" list is your to-do list for
step 5.

## 3. Create the course in Studio

1. Sign in to Studio (preprod).
2. **New course**. Fill in:
   - **Course name**: the Moodle full name (for example `Linux Fundamentals`).
   - **Organization**: `OpsWerks`.
   - **Course number**: the Moodle short name (for example `A11-FND-LNX01`).
   - **Course run**: the run, for example `2026`.
3. **Create**. You land on the empty course outline.

If the course already exists (a second attempt), open it instead: the import in step 4
replaces all of its content.

## 4. Import the archive

1. In the course, open **Tools › Import**.
2. **Choose a file to import**, pick `out/<course>/<course>-<run>.tar.gz`, then
   **Replace my course with the one above**.
3. Wait for all steps to turn green: Uploading, Unpacking, Verifying, Updating course. It takes a
   minute or two.
4. **View updated outline**. You should see the same sections as in Moodle.

If it stops at **Unpacking** with "Uploaded tar file not found", see
[Troubleshooting](#troubleshooting).

## 5. Do the manual follow-ups in Studio

Work through **every** item under "Manual follow-up in Studio" in `conversion-report.md`. The
kinds you will meet:

### 5a. Prerequisites (access restrictions)

For each item "**subsection B**: Set prerequisite '**A**' with minimum score 100%":

1. On the course outline, on subsection **A** (the one that must be done first), open
   **⋮ › Configure › Advanced** and tick **Use as prerequisite**. **Save**.
2. On subsection **B**, open **⋮ › Configure › Advanced**. Under **Limit access**, pick **A** as
   the prerequisite, set **Minimum score** to **100** and **Minimum completion** to **0**.
   **Save**.

100% matters: Moodle required every "I agree" box to be ticked, and that is a score of 100%.

"Moodle required completing X, Y, Z. OpenLMS allows one prerequisite per subsection" means
OpenLMS can't express the rule. Leave it open; it is a known gap.

### 5b. Due dates for the new run

Moodle dates belong to the old run and were left out. For every graded subsection, and every
subsection listed under "Dates from the Moodle run":

1. **⋮ › Configure › Basic**, set **Due date** (and **Release date** if it should open later)
   for the new run. **Save**.

For each assignment (an Open Response Assessment): open its unit, **Edit** the component,
**Settings › Schedule**, set **Response due**. **Save**.

Until a due date is set, answers that Moodle showed "after the quiz closed" stay hidden.

### 5c. Credentials in the content

For each "Possible password …": open the unit, **Edit** the component, and rewrite that line so
it no longer contains the credential, for example "Ask your instructor for the lab password."
**Save**. The checker fails while any credential is left.

### 5d. Broken links and missing files

- "Relative link … won't resolve": edit the component and remove the link (it was already broken
  in Moodle) or point it at the right page.
- "Embedded file … is not in the backup": upload the file under **Content › Files** and fix the
  link in the component.
- "Link to another Moodle item … removed": edit the component and link to the matching unit in
  OpenLMS, or remove the sentence.

### 5e. Everything else

Items such as "Free-text question not converted" are known gaps: there is nothing to do in
Studio. They are listed in the known-gaps file (step 7).

### 5f. Publish

On the course outline, **Publish** every section (or each subsection with unpublished changes).
Learners only see published content, and the checker flags anything unpublished.

## 6. Export the course from Studio

1. **Tools › Export › Export course content**.
2. When it says "Your exported course can now be downloaded", **Download exported course**. The
   file is named like `course.xxxxxxxx.tar.gz`.

## 7. Run the checker

The first time a course is migrated, create its known-gaps file from the Moodle backup:

```bash
uv run mbz2openlms gaps init ~/Downloads/backup-moodle2-course-131-....mbz
```

This writes `known-gaps/<course>.toml` listing the Moodle features with no OpenLMS equivalent
(for example quiz time limits, free-text survey questions). Send it to Bay and Geo for review:
they delete what is not acceptable and fill in "Reviewed by". Linux Fundamentals already has one.

Then check:

```bash
uv run mbz2openlms check ~/Downloads/backup-moodle2-course-131-....mbz \
  --export ~/Downloads/course.xxxxxxxx.tar.gz
```

It prints `PASS` or `FAIL` and writes `out/<course>/check-report.md` (shareable) and
`check.json`. Exit status 0 is PASS, 1 is FAIL, 2 is an error (unreadable file and so on).

Read the report:

| Section | Meaning | What to do |
|---|---|---|
| ❌ Fail | Something differs from Moodle, or breaks a review rule | Fix it in Studio (step 5), publish, export again, and re-run the check |
| ⚠️ Warning | Worth a look, doesn't block | Read each one. "External host not yet reviewed" waits on the review-rules document |
| 📝 Known gap | A listed, accepted difference | Nothing |
| ⏸ Not checked | Can't be read from an export | **Do the checklist below** |
| Stale known gaps | Entries in the known-gaps file that no longer match | Tell whoever owns the file |

### Prerequisite checklist (export mode)

A Studio export doesn't contain subsection prerequisites, so the checker lists them as "Not
checked" and still says PASS. **PASS from an export does not cover them.** For each "Not checked"
line, open the named subsection in Studio, **⋮ › Configure › Advanced**, and confirm it requires
the named prerequisite with a minimum score of 100%. Tick each one off in your migration notes.

(With a Studio API client the checker reads prerequisites itself; see
[checker.md](checker.md#studio-api-mode). Instructors don't need it.)

## 8. Done

The migration is done when:

- [ ] `mbz2openlms check` says **PASS**.
- [ ] Every "Not checked" prerequisite is ticked off by hand (step 7).
- [ ] Every warning has been read.
- [ ] The course's known-gaps file has been reviewed by Bay and Geo.

Send `check-report.md` and `conversion-report.md` to the course owner. Don't send the
`.tar.gz`, `inventory.json` or the Moodle backup.

## What carries over and what doesn't

| Moodle | OpenLMS | Notes |
|---|---|---|
| Section, subsection | Section, subsection | A subsection is split wherever an activity is gated on finishing an earlier one: OpenLMS gates whole subsections |
| Page, label, URL | Unit with the text or link | |
| File, folder | Files & Uploads, listed in a unit | Folder subfolders are flattened |
| Book | Subsection, one unit per chapter | Hidden chapters are left out |
| Quiz: multiple choice, true/false, short answer, numerical | Problems with the same answers and marks | Checkbox partial credit becomes all-or-nothing; wildcard short answers need a manual fix |
| Quiz: random questions | Problem Bank that shows each learner N of the pool | |
| Quiz: essay, assignment | Open Response Assessment, staff-graded | Not auto-graded |
| Quiz: description | Text in the unit | |
| Feedback with only "I agree" boxes | Checkbox problem, all boxes required, set as a prerequisite | Optional statements become required |
| Feedback with rating questions | Survey component | Free-text questions are not carried over |
| Gradebook (natural) | Grading policy with the same weights; pass mark as the course cutoff | One cutoff for the course |
| Access restriction "complete X" | Subsection prerequisite at 100% | Manual, step 5a. Only one per subsection |
| Access restriction by date | Subsection release / due dates | Manual, step 5b |
| Quiz time limit | Not carried over | Needs timed exams on OpenLMS (platform decision) |
| Quiz password, network or browser restriction | Not carried over | |
| Matching, cloze, drag-and-drop and other question types | Not carried over | Rebuild by hand |
| Forum, choice, lesson, workshop, H5P, SCORM, LTI, glossary, wiki, database | Not carried over | Rebuild by hand; listed in `conversion-report.md` |
| Learner data (enrolments, attempts, grades) | Not carried over | Out of scope |

`inventory.md` shows the planned target and status of every activity in your course before
you import anything.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Import stops at **Unpacking** with "Uploaded tar file not found" | Preprod platform issue: the uploaded file is saved on a different pod from the one that unpacks it (incident 2026-10-16, fix `d24ced1`) | Not your file. Ask the platform team to confirm the course import storage fix is live on preprod, then import again |
| Import fails at **Verifying** | The archive is damaged or not a course export | Run `convert` again and import the new `.tar.gz`, not the backup or an `.mbz` |
| `convert` says "moodle_backup.xml not found" or "Not a tar or zip archive" | The file isn't a Moodle course backup | Download the `.mbz` again from the Restore page (step 1) |
| `convert` or `inventory.md` says **Includes user data** | "Include enrolled users" was left ticked | Take the backup again without users (step 1) |
| Check: "question text not found" or "answers differ" | A problem was edited or deleted in Studio | Compare with Moodle and fix the problem in Studio, or convert and import again |
| Check: "not found in OpenLMS section" | A unit or subsection was renamed or deleted | Restore the Moodle title in Studio, or import again |
| Check: "unit is not in the Moodle course" | A unit was added in Studio | Remove it, or accept it with the course owner |
| Check: "no due date set for the new run" (warning) or "due … is in the past" (fail) | Step 5b not done, or done with an old date | Set a future due date and publish |
| Check: "possible password …" | Step 5c not done | Rewrite that line in Studio |
| Check: "Moodle link left over" | A link still points to Moodle | Step 5d |
| Check: "external host not yet reviewed" (warning) | The review-rules document has not listed the host yet | Nothing; listed for the reviewers |
| Check: "unpublished changes" | Edits were saved but not published | Publish, export again, re-run the check |
| Check report lists **Stale known gaps** | The known-gaps file lists something that no longer fails | Tell the file's owner; nothing is wrong with the course |
| `check` exits with status 2 | The backup or export can't be read | Check the paths. The export is the `.tar.gz` from Studio's **Tools › Export** |
| A feature in your course isn't in the table above | The tool hasn't met it before | It is listed in `conversion-report.md` as a manual follow-up; rebuild it by hand and tell the maintainers |
