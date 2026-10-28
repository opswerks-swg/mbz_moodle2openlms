# Route decision: Moodle → OpenLMS

**Decision: route 1.** Take a Moodle course backup (`.mbz`, without users), convert it with our
own Python CLI (`mbz2openlms convert`) to an OLX archive, and import that through Studio's
**Tools › Import**. The other routes were compared on the pilot course, Linux Fundamentals
(course 131).

Status: ⏳ awaiting review by Bay and Geo. Route 1 and route 2 were measured on course 131
(below).

## Requirements the route must meet

1. Structure, content, quizzes and assignments match the Moodle course, and an automated check
   can confirm it.
2. An instructor can run it without platform access (no kubectl, no database, no admin token).
3. Anything that doesn't carry over is listed for manual follow-up.
4. No learner data (out of scope).

## Routes compared

| # | Route | Fidelity on course 131 | Effort | Instructor can run it? | Verdict |
|---|---|---|---|---|---|
| 1 | **Moodle backup (.mbz) → `mbz2openlms` → OLX → Studio import** | High: the backup holds the full structure, page and book HTML, files, the whole question bank (with versions and random-question filters), assignment settings, Feedback items, access restrictions and the gradebook. Course 131 converts with every question, answer key and both random pools intact (`check` passes). | Medium–high: we own the converter (about 5,800 lines of Python with the checker) | Yes: Moodle backup, one command, Studio import | **Chosen** |
| 2 | Moodle IMS Common Cartridge export → `cc2olx` (openedx) → OLX → import | Medium. Moodle's CC 1.1 export covers Forum, Label, LTI, Page, URL and Quiz (partly): **no Book, Assignment, Feedback, Files or Question bank**. `cc2olx`'s README says it doesn't convert images. No random-question pools, no gradebook, no access restrictions. | Low to try | Yes | Rejected: misses most of course 131 (see the measured bake-off) |
| 3 | Moodle web service API (`core_course_get_contents`, …) → OLX | Medium: structure and content come through, but quiz questions with answer keys need a plugin, and random-question filters aren't exposed | Medium | Only with an admin-issued token | Rejected as the converter. REST is enabled on Moodle (a probe returned `invalidtoken`, not "disabled"), so it stays an option for a future source-side check |
| 4 | Direct Moodle database extraction | High | Medium | No: needs database access | Rejected for handover. Possible for a one-off audit |
| 5 | Wrap the course as SCORM, or keep it in Moodle and link it in over LTI | Low: a black box with no native problems, grading or checks | Low | — | Rejected. Exception: SCORM packages already in Moodle can move over as-is to the SCORM XBlock |
| — | Existing tooling: `moodle2edx` (MIT, Python 2, unmaintained) | Pre-Moodle-4 format: no question bank entries or versions, no Moodle 5 subsections | — | — | Rejected; used only as reference |

The import step has three options:

- **Studio UI** (Tools › Import), for instructors. **Chosen.**
- The CMS import REST API (`/api/courses/v0/import/<course>/`). It works with an OAuth client and is used by `mbz2openlms e2e` on test courses.
- `manage.py import` via kubectl, for the platform team only.

## Why route 1

- **Only the backup holds everything course 131 uses.** The Quiz draws 19 of 20 "Easy" and 3 of
  7 "Medium" questions per learner. The three Integrity Agreements are Feedback activities that
  gate the assessments. The Practical is an essay graded out of 80. KKE Completion is a file
  upload assignment. Grading is a 50/50 split with an 85% pass mark. A CC export loses the random
  pools, the Feedback activities, the assignment and the grading.
- **It is checkable.** The same backup feeds an independent checker (`mbz2openlms check`), which
  compares every question's answer key, every pool, the grading and the review rules. Route 2's
  output can be checked the same way, which is how it was measured.
- **Instructors can run it** with the access they have: Moodle backup, Studio import, Studio
  export.

Trade-offs accepted:

- We maintain a converter. It is covered by 80+ automated tests, including a real-course run
  and an end-to-end run against a real Studio.
- Activity types the pilot doesn't use (forum, lesson, workshop, H5P, SCORM, LTI, …) aren't
  converted. They are listed as manual follow-ups, and the converter can grow when a course
  needs them.
- Moodle features with no Open edX equivalent (time limits while timed exams are off, free-text
  survey questions, multi-activity restrictions) are known gaps, listed per course.

## Measured bake-off on course 131 (route 1 vs route 2)

Inputs:

- **Route 1:** `backup-moodle2-course-131-a11-fnd-lnx01-20261027-1258-nu.mbz` (no user data),
  converted by `mbz2openlms convert`.
- **Route 2:** `backup-moodle2-course-131-a11-fnd-lnx01-20261028-1022.imscc`. This is IMS CC
  1.1 from Moodle 5.1.1, converted by openedx `cc2olx` at commit `7649be5` (2026-10-28).

The route-2 run is recorded in
`../ims_common_cartridge_moodle2openlms/docs/route2-spike-findings.md`. The cartridge counts
below were re-measured here from its `imsmanifest.xml`.

Measures that don't depend on where things are placed come first. Neither route renames items,
but `cc2olx` drops them, and a title-based placement score would hide by how much.

| Measure | Route 1 (`.mbz` → `mbz2openlms`) | Route 2 (CC → `cc2olx`) |
|---|---|---|
| Moodle course text present (3,413 words: pages, book, intros, instructions, agreement statements, survey and quiz questions and answers) | **99.2%** | **≤ 5.4%** (all the text in the cartridge: the one page) |
| Learner-facing activities carried (of 13) | 13 | 1 (the page "Before you begin") |
| Section / subsection structure | Sections and subsections, split where Moodle gates an activity | 6 flat chapters, 5 with an empty subsection; Moodle subsections become sections |
| Quiz questions with answer keys (29 used by the 3 quizzes) | 29: every one matches Moodle's answers and marks | 0. The cartridge has no QTI at all, even for the fixed-slot quizzes |
| Random pools (19 of 20, 3 of 7) | 2 Problem Banks | 0 |
| Assignment → ORA (file upload, 2 files) | yes | no |
| Integrity agreements (3) / survey (1) | 3 checkbox problems / 1 Survey | 0 / 0 |
| Grading policy (50/50, cutoff 85%) | yes | none (`advanced_modules: []`, no grading policy) |
| Embedded image | uploaded, link rewritten | not converted (cc2olx doesn't convert images); broken relative link |
| Course identity | the Moodle short name | `org`/`Some_cc_Course` placeholders |
| Learner data in the input | none (backup without users) | **74 learner submission images**, many named after learners, inside the cartridge: Moodle's CC export has no "without users" option |
| Checker result | PASS after the runbook's follow-ups (11 reviewed known gaps); e2e on a real Studio: 10 of 10 steps | Not run: with 1 of 13 activities there is nothing to compare for most checks |

**Result:** route 2 can't meet "structure, content, quizzes and assignments match" for course
131. Everything except one page would be rebuilt by hand. Its input also carries personal data
that the route-1 backup leaves out.

Route 2 may still suit a course made only of pages, URLs, labels and forums, the activities
Moodle's CC export covers. The Course Inventory spreadsheet shows whether any such courses
exist. Route 1 handles those activities too (forum aside: a manual follow-up either way), so one
route is enough.
