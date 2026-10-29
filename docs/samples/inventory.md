# Inventory: Synthetic Linux (SYN-LNX 01)

Backup `backup-moodle2-course-syn-lnx-01`, Moodle 5.1 (Build: test), taken 2026-10-27 04:59 UTC. No user data.

## Summary

|  | Count |
|---|---|
| Sections | 3 |
| Subsections | 2 |
| Activities | 12: 2 subsection, 2 feedback, 2 quiz, 1 page, 1 url, 1 book, 1 assign, 1 forum, 1 qbank |
| Questions | 13 bank entries (14 saved versions): 4 multichoice_single, 2 truefalse, 1 multichoice_multi, 1 shortanswer, 1 numerical, 1 essay, 1 description, 1 match |
| Files | 2 (1 missing) |
| Links and embeds | 2 pluginfile, 2 external, 1 relative, 1 moodle_link |

## Outline and target

| Moodle | OpenLMS target | Status |
|---|---|---|
| **Intro** (section) | Section | ✅ supported |
| Welcome (page) | Unit with an HTML component | ✅ supported |
| Docs (url) | Unit with a link | ✅ supported |
| Materials (book) | Subsection with one unit per chapter | ✅ supported |
| Upload (assign) | Open Response Assessment (ORA), staff-graded | ⚠️ partial |
| Chat (forum) | Discussion topic | ❌ gap |
| Bank (qbank) | Not learner-facing (source of quiz questions) | — |
| **Assessment** (section) | Section | ✅ supported |
| Final (subsection) | Subsection | ✅ supported |
| ↳ Agreement (feedback) | Checkbox problem, every box required | ⚠️ partial |
| ↳ Exam (quiz) | Graded subsection with problem components | ❌ gap |
| Practice (subsection) | Subsection | ✅ supported |
| ↳ Practice quiz (quiz) | Graded subsection with problem components | ✅ supported |
| **Survey** (section) | Section | ✅ supported |
| Survey (feedback) | Survey component (rating questions) | ⚠️ partial |

## Activities: notes

| Activity | Notes |
|---|---|
| url 'Docs' | The link goes through the review-rules scan. |
| assign 'Upload' | Staff grade submissions in ORA instead of the Moodle grader. File upload: up to 2 file(s) of 0 KB, types '.pdf'. |
| forum 'Chat' | Not converted; posts never carry over. |
| feedback 'Agreement' | The 'page after submit' message has no equivalent. Optional statements become required. |
| quiz 'Exam' | 2 random slot(s): a Problem Bank shows each learner N problems from the pool. Time limit 30 min needs timed exams on OpenLMS. Open/close dates belong to the old run: set new dates in Studio. Access restriction: 'Agreement' is complete. Closest match: a subsection prerequisite. |
| quiz 'Practice quiz' | Quiz grade is 0 in Moodle, so the subsection is ungraded. |
| feedback 'Survey' | 1 free-text question(s) have no equivalent. The 'page after submit' message has no equivalent. Access restriction: ('Exam' is complete AND 'Upload' is complete). Closest match: a subsection prerequisite. |

## Quizzes

### Exam

Grade 100, 10 slot(s), attempts 1, time limit 30 min, opens 2026-07-17 08:00 UTC, closes —.

- Fixed questions: 1 description, 1 multichoice_single, 1 multichoice_multi, 1 truefalse, 1 shortanswer, 1 numerical, 1 essay, 1 match
- Random: 2 from a pool of 3 (tags: Easy; mark 1)

### Practice quiz

Grade 0, 1 slot(s), attempts 1, time limit none min, opens —, closes —.

- Fixed questions: 1 truefalse

## Question types

| Type | Count | OpenLMS | Status |
|---|---|---|---|
| multichoice_single | 4 | Multiple choice problem | ✅ supported |
| multichoice_multi | 1 | Checkboxes problem | ⚠️ partial |
| truefalse | 2 | Multiple choice problem (True/False) | ✅ supported |
| shortanswer | 1 | Text input problem | ✅ supported |
| numerical | 1 | Numerical input problem | ✅ supported |
| essay | 1 | ORA, staff-graded | ⚠️ partial |
| description | 1 | HTML component | ✅ supported |
| match | 1 | No equivalent | ❌ gap |

## Gradebook

Aggregation: natural.

| Item | Type | Max | Pass | Weight |
|---|---|---|---|---|
| assign 'Upload' | value | 50 | 25 | 33% |
| quiz 'Exam' | value | 100 | 50 | 67% |

## External hosts

| Host | Links |
|---|---|
| docs.example.com | 2 |

## Gaps and manual follow-ups

| Where | Status | Detail |
|---|---|---|
| assign 'Upload' | ⚠️ partial | Staff grade submissions in ORA instead of the Moodle grader. File upload: up to 2 file(s) of 0 KB, types '.pdf'. |
| forum 'Chat' | ❌ gap | Not converted; posts never carry over. |
| feedback 'Agreement' | ⚠️ partial | The 'page after submit' message has no equivalent. Optional statements become required. |
| quiz 'Exam' | ❌ gap | 2 random slot(s): a Problem Bank shows each learner N problems from the pool. Time limit 30 min needs timed exams on OpenLMS. Open/close dates belong to the old run: set new dates in Studio. Access restriction: 'Agreement' is complete. Closest match: a subsection prerequisite. |
| feedback 'Survey' | ⚠️ partial | 1 free-text question(s) have no equivalent. The 'page after submit' message has no equivalent. Access restriction: ('Exam' is complete AND 'Upload' is complete). Closest match: a subsection prerequisite. |
| 1 question(s) of type multichoice_multi | ⚠️ partial | → Checkboxes problem. Weighted partial credit becomes all-or-nothing. |
| 1 question(s) of type essay | ⚠️ partial | → ORA, staff-graded. Not auto-graded: staff grade it in ORA. |
| 1 question(s) of type match | ❌ gap | → No equivalent. Not converted: rebuild by hand. |
| page 'Welcome' content | ❌ gap | Embedded file 'gone.png' is not in the backup. |
| page 'Welcome' content | ⚠️ partial | Relative link won't resolve on OpenLMS. |
| page 'Welcome' content | ⚠️ partial | Link to another Moodle item: re-link it. |
