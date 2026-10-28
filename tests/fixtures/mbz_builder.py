"""Build small synthetic Moodle 5 course backups for tests.

``sample_backup(dest)`` writes a course that covers the edge cases the reader, converter and
checker must handle:

  Intro (section 0, summary)
    page "Welcome"       embedded image (present) + one missing, external link, Moodle link
    url "Docs"           external URL
    book "Materials"     two chapters and a hidden one
    assign "Upload"      file + online text, graded out of 50, pass 25, due date
    forum "Chat"         no OpenLMS equivalent
    qbank "Bank"         not learner-facing
  Assessment (section 1)
    subsection "Final" (its section has a lower <number> than "Practice"; order follows the
    parent's <sequence>):
      feedback "Agreement"   two "I agree" checkboxes, one optional; page after submit
      quiz "Exam"            gated on Agreement; fixed: single, multi, true/false, short answer,
                             numerical, essay, description, match (not converted); random: 2 of
                             a 3-question "Easy" pool; 30 min time limit; graded out of 100
    subsection "Practice":
      quiz "Practice quiz"   ungraded; one fixed question pinned to version 1 of an entry with
                             a newer version
  Survey (section 2)
    feedback "Survey"     two rating questions + one free-text, gated on Exam AND Upload

``SECRET_ANSWER`` is the text of a correct answer: reports must never contain it.
"""

from __future__ import annotations

import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

SECRET_ANSWER = "SECRET-ANSWER-PARIS"
CREDENTIAL = "password: Hunter2Secret!"
IMAGE_HASH = "ab" + "1" * 38
MISSING_HASH = "cd" + "2" * 38
NULL = "$@NULL@$"

COURSE_CONTEXT = 50
EXAM, PRACTICE, AGREEMENT, SURVEY, UPLOAD = 20, 21, 19, 30, 13


def x(value: str) -> str:
    return escape(value)


@dataclass
class Builder:
    root: Path
    activities: list[tuple[int, str, str, int]] = field(default_factory=list)
    sections: list[tuple[int, str, int | None]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + text, encoding="utf-8")

    def section(
        self,
        sid: int,
        number: int,
        name: str,
        sequence: list[int],
        parent_cmid: int | None = None,
        summary: str = "",
    ) -> None:
        self.sections.append((sid, name, parent_cmid))
        self.write(
            f"sections/section_{sid}/section.xml",
            f"""<section id="{sid}">
  <number>{number}</number>
  <name>{x(name)}</name>
  <summary>{x(summary)}</summary>
  <sequence>{",".join(map(str, sequence))}</sequence>
  <visible>1</visible>
  <availabilityjson>{x('{"op":"&","c":[],"showc":[]}')}</availabilityjson>
</section>""",
        )

    def activity(
        self,
        cmid: int,
        modname: str,
        title: str,
        section: int,
        body: str,
        context: int | None = None,
        availability: dict | None = None,
        grade: tuple[int, float, float] | None = None,  # (gradetype, max, pass)
        visible: bool = True,
    ) -> None:
        self.activities.append((cmid, modname, title, section))
        folder = f"activities/{modname}_{cmid}"
        avail = x(json.dumps(availability)) if availability else NULL
        self.write(
            f"{folder}/module.xml",
            f"""<module id="{cmid}" version="2025100600">
  <modulename>{modname}</modulename>
  <visible>{int(visible)}</visible>
  <completion>2</completion>
  <availability>{avail}</availability>
</module>""",
        )
        self.write(
            f"{folder}/{modname}.xml",
            f"""<activity id="{cmid}" moduleid="{cmid}" modulename="{modname}" contextid="{context or 1000 + cmid}">
  <{modname} id="{cmid}">
    <name>{x(title)}</name>
{body}
  </{modname}>
</activity>""",
        )
        if grade:
            gradetype, grademax, gradepass = grade
            self.write(
                f"{folder}/grades.xml",
                f"""<activity_gradebook><grade_items><grade_item id="{cmid}">
  <categoryid>1</categoryid><itemname>{x(title)}</itemname><itemtype>mod</itemtype>
  <itemmodule>{modname}</itemmodule><iteminstance>{cmid}</iteminstance>
  <gradetype>{gradetype}</gradetype><grademax>{grademax}</grademax><grademin>0</grademin>
  <gradepass>{gradepass}</gradepass><aggregationcoef2>0</aggregationcoef2>
  <weightoverride>0</weightoverride><hidden>0</hidden>
</grade_item></grade_items></activity_gradebook>""",
            )

    def finish(self, fullname: str, shortname: str) -> None:
        acts = "".join(
            f"""<activity><moduleid>{c}</moduleid><sectionid>{s}</sectionid>
<modulename>{m}</modulename><title>{x(t)}</title><directory>activities/{m}_{c}</directory>
</activity>"""
            for c, m, t, s in self.activities
        )
        secs = "".join(
            f"""<section><sectionid>{sid}</sectionid><title>{x(name)}</title>
<directory>sections/section_{sid}</directory>
<parentcmid>{parent if parent else ""}</parentcmid></section>"""
            for sid, name, parent in self.sections
        )
        self.write(
            "moodle_backup.xml",
            f"""<moodle_backup><information>
  <name>synthetic.mbz</name>
  <moodle_release>5.1 (Build: test)</moodle_release>
  <backup_date>1793077181</backup_date>
  <original_wwwroot>https://moodle.example.org</original_wwwroot>
  <original_course_id>7</original_course_id>
  <original_course_fullname>{x(fullname)}</original_course_fullname>
  <original_course_shortname>{x(shortname)}</original_course_shortname>
  <original_course_startdate>1783872000</original_course_startdate>
  <original_course_contextid>{COURSE_CONTEXT}</original_course_contextid>
  <settings><setting><level>root</level><name>users</name><value>0</value></setting></settings>
  <contents><activities>{acts}</activities><sections>{secs}</sections></contents>
</information></moodle_backup>""",
        )


# -- questions --------------------------------------------------------------------------------


def _answers(answers: list[tuple[str, float]]) -> str:
    return "".join(
        f"""<answer id="{900 + i}"><answertext>{x(text)}</answertext><answerformat>1</answerformat>
<fraction>{fraction}</fraction><feedback></feedback></answer>"""
        for i, (text, fraction) in enumerate(answers)
    )


def question(
    qid: int,
    qtype: str,
    name: str,
    text: str,
    answers: list[tuple[str, float]] = (),
    options: str = "",
    tags: list[tuple[int, str]] = (),
) -> str:
    tag_xml = "".join(
        f'<tag id="{t}"><name>{n}</name><rawname>{n}</rawname></tag>' for t, n in tags
    )
    return f"""<question id="{qid}">
  <name>{x(name)}</name><qtype>{qtype}</qtype>
  <questiontext>{x(text)}</questiontext><generalfeedback></generalfeedback>
  <defaultmark>1</defaultmark><penalty>0</penalty>
  <plugin_qtype_{qtype}_question>
    <answers>{_answers(list(answers))}</answers>
    {options}
  </plugin_qtype_{qtype}_question>
  <tags>{tag_xml}</tags>
</question>"""


def entry(eid: int, *versions: tuple[int, str, str]) -> str:
    """versions: (version number, status, question xml)."""
    body = "".join(
        f"""<question_versions><version>{v}</version><status>{status}</status>
<questions>{q}</questions></question_versions>"""
        for v, status, q in versions
    )
    return f"""<question_bank_entry id="{eid}"><idnumber>{NULL}</idnumber>
<question_version>{body}</question_version></question_bank_entry>"""


def _questions_xml() -> str:
    single = "<multichoice><single>1</single><shuffleanswers>1</shuffleanswers></multichoice>"
    multi = "<multichoice><single>0</single><shuffleanswers>0</shuffleanswers></multichoice>"
    easy = [(11, "Easy")]
    fixed = [
        entry(1, (1, "ready", question(101, "multichoice", "Capital", "<p>Capital of France?</p>",
              [(f"<p>{SECRET_ANSWER}</p>", 1.0), ("<p>Lyon</p>", 0.0)], single))),
        entry(2, (1, "ready", question(102, "multichoice", "Pick two", "<p>Pick the primes</p>",
              [("2", 0.5), ("3", 0.5), ("4", 0.0)], multi))),
        entry(3, (1, "ready", question(103, "truefalse", "Sky", "<p>The sky is blue.</p>",
              [("True", 1.0), ("False", 0.0)]))),
        entry(4, (1, "ready", question(104, "shortanswer", "Command", "<p>Command to list files</p>",
              [("ls", 1.0), ("dir", 1.0), ("cat", 0.0)], "<shortanswer><usecase>0</usecase></shortanswer>"))),
        entry(5, (1, "ready", question(105, "numerical", "Sum", "<p>What is 2 + 2?</p>",
              [("4", 1.0)], "<numerical_records><numerical_record><tolerance>0.1</tolerance></numerical_record></numerical_records>"))),
        entry(6, (1, "ready", question(106, "essay", "Essay", "<p>Explain the boot process.</p>",
              [], "<essay><responseformat>editor</responseformat><responserequired>1</responserequired><attachments>0</attachments></essay>"))),
        entry(7, (1, "ready", question(107, "description", "Read me", "<p>Read the rules first.</p>"))),
        entry(8, (1, "ready", question(108, "match", "Match", "<p>Match the pairs</p>"))),
        # Pinned to version 1 by the practice quiz; version 2 is newer.
        entry(9, (1, "ready", question(109, "truefalse", "Old", "<p>Old wording of the fact.</p>",
              [("True", 1.0), ("False", 0.0)])),
              (2, "ready", question(110, "truefalse", "New", "<p>New wording of the fact.</p>",
              [("True", 0.0), ("False", 1.0)]))),
    ]  # fmt: skip
    pool = [
        entry(20 + i, (1, "ready", question(120 + i, "multichoice", f"Easy {i}",
              f"<p>Easy question number {i} about Linux</p>",
              [(f"<p>right {i}</p>", 1.0), (f"<p>wrong {i}</p>", 0.0)], single, easy)))
        for i in range(3)
    ]  # fmt: skip
    # A hidden-only entry tagged Easy: never drawn.
    pool.append(entry(29, (1, "hidden", question(129, "multichoice", "Hidden", "<p>Hidden</p>",
                [("a", 1.0)], single, easy))))  # fmt: skip
    return f"""<question_categories>
<question_category id="5"><name>Default</name><contextid>{COURSE_CONTEXT}</contextid>
<contextlevel>50</contextlevel><parent>0</parent>
<question_bank_entries>{"".join(fixed + pool)}</question_bank_entries></question_category>
</question_categories>"""


def _fixed_slot(slot: int, entry_id: int, mark: float, version: int | None = None) -> str:
    v = version if version is not None else NULL
    return f"""<question_instance id="{300 + slot}"><slot>{slot}</slot><page>1</page>
<maxmark>{mark}</maxmark><requireprevious>0</requireprevious>
<question_reference id="{400 + slot}"><questionbankentryid>{entry_id}</questionbankentryid>
<version>{v}</version></question_reference></question_instance>"""


def _random_slot(slot: int, mark: float) -> str:
    condition = {
        "filter": {
            "category": {"jointype": 1, "values": [5], "filteroptions": {"includesubcategories": False}},
            "qtagids": {"jointype": 1, "values": [11]},
        },
        "jointype": 2,
    }  # fmt: skip
    return f"""<question_instance id="{300 + slot}"><slot>{slot}</slot><page>2</page>
<maxmark>{mark}</maxmark><requireprevious>0</requireprevious>
<question_set_reference id="{400 + slot}"><filtercondition>{x(json.dumps(condition))}</filtercondition>
</question_set_reference></question_instance>"""


def _quiz(slots: str, grade: float, timelimit: int, opens: int = 0) -> str:
    return f"""    <intro></intro>
    <timeopen>{opens}</timeopen><timeclose>0</timeclose><timelimit>{timelimit}</timelimit>
    <attempts_number>1</attempts_number><shuffleanswers>1</shuffleanswers>
    <questionsperpage>1</questionsperpage><grade>{grade}</grade><sumgrades>10</sumgrades>
    <password></password><subnet></subnet><browsersecurity>-</browsersecurity>
    <reviewrightanswer>16</reviewrightanswer><reviewcorrectness>16</reviewcorrectness>
    <reviewspecificfeedback>16</reviewspecificfeedback>
    <question_instances>{slots}</question_instances>"""


def _item(iid: int, pos: int, typ: str, name: str, presentation: str, required: int = 1) -> str:
    return f"""<item id="{iid}"><name>{x(name)}</name><presentation>{x(presentation)}</presentation>
<typ>{typ}</typ><position>{pos}</position><required>{required}</required></item>"""


def sample_backup(dest: Path) -> Path:
    """Write the synthetic course as an extracted backup in ``dest`` and return ``dest``."""
    b = Builder(dest)
    image = '<img src="@@PLUGINFILE@@/diagram%201.png" alt="d">'
    missing = '<img src="@@PLUGINFILE@@/gone.png">'
    welcome = (
        f"<p>Welcome to the course, read everything carefully.</p>{image}{missing}"
        '<p>See <a href="https://docs.example.com/guide">the guide</a> and '
        '<a href="$@QUIZVIEWBYID*20@$">the exam</a>.</p>'
        f"<p>Lab login {CREDENTIAL}</p>"
    )
    b.activity(10, "page", "Welcome", 1, f"<intro></intro><content>{x(welcome)}</content>", 1010)
    b.activity(
        11, "url", "Docs", 1, "<intro></intro><externalurl>https://docs.example.com/</externalurl>"
    )
    chapters = "".join(
        f"""<chapter id="{i}"><pagenum>{i}</pagenum><subchapter>0</subchapter><hidden>{h}</hidden>
<title>{t}</title><content>{x(f"<p>{c}</p>")}</content></chapter>"""
        for i, t, c, h in [
            (1, "Basics", "Chapter one explains the shell and its prompt.", 0),
            (2, "Files", "Chapter two covers files, directories and permissions.", 0),
            (3, "Draft", "Unfinished chapter.", 1),
        ]
    )
    b.activity(12, "book", "Materials", 1, f"<intro></intro><chapters>{chapters}</chapters>")
    assign = f"""    <intro>{x("<p>Upload your lab report as a PDF.</p>")}</intro><activity></activity>
    <allowsubmissionsfromdate>0</allowsubmissionsfromdate><duedate>1784275200</duedate>
    <cutoffdate>0</cutoffdate><grade>50</grade><teamsubmission>0</teamsubmission>
    <plugin_configs>
      <plugin_config><plugin>file</plugin><subtype>assignsubmission</subtype><name>enabled</name><value>1</value></plugin_config>
      <plugin_config><plugin>file</plugin><subtype>assignsubmission</subtype><name>maxfilesubmissions</name><value>2</value></plugin_config>
      <plugin_config><plugin>file</plugin><subtype>assignsubmission</subtype><name>filetypeslist</name><value>.pdf</value></plugin_config>
      <plugin_config><plugin>onlinetext</plugin><subtype>assignsubmission</subtype><name>enabled</name><value>1</value></plugin_config>
    </plugin_configs>"""  # fmt: skip
    b.activity(UPLOAD, "assign", "Upload", 1, assign, grade=(1, 50.0, 25.0))
    b.activity(14, "forum", "Chat", 1, "<intro></intro><type>general</type>")
    b.activity(15, "qbank", "Bank", 1, "<intro></intro><type>standard</type>", COURSE_CONTEXT)
    b.section(1, 0, "Intro", [10, 11, 12, UPLOAD, 14, 15], summary="<p>Start here first.</p>")

    # Assessment: the parent sequence lists Final (16) before Practice (17).
    b.activity(16, "subsection", "Final", 2, "")
    b.activity(17, "subsection", "Practice", 2, "")
    b.section(2, 1, "Assessment", [16, 17])
    agree = "".join(
        _item(i, p, "multichoice", n, "c>>>>>I agree", r)
        for i, p, n, r in [(51, 1, "I will work alone.", 1), (52, 2, "I will not use AI tools.", 0)]
    )
    after = x("<p>Thank you.</p>")
    b.activity(
        AGREEMENT,
        "feedback",
        "Agreement",
        3,
        f"<intro>{x('<p>Read and accept.</p>')}</intro><page_after_submit>{after}</page_after_submit>"
        f"<timeopen>0</timeopen><timeclose>0</timeclose><items>{agree}</items>",
    )
    slots = "".join(
        [
            _fixed_slot(1, 7, 0),
            _fixed_slot(2, 1, 2),
            _fixed_slot(3, 2, 1),
            _fixed_slot(4, 3, 1),
            _fixed_slot(5, 4, 1),
            _fixed_slot(6, 5, 1),
            _fixed_slot(7, 6, 5),
            _fixed_slot(8, 8, 1),
            _random_slot(9, 1),
            _random_slot(10, 1),
        ]
    )
    b.activity(
        EXAM,
        "quiz",
        "Exam",
        3,
        _quiz(slots, 100, 1800, opens=1784275200),
        availability={"op": "&", "c": [{"type": "completion", "cm": AGREEMENT, "e": 1}]},
        grade=(1, 100.0, 50.0),
    )
    b.section(3, 5, "Final", [AGREEMENT, EXAM], parent_cmid=16)
    b.activity(PRACTICE, "quiz", "Practice quiz", 4, _quiz(_fixed_slot(1, 9, 1, 1), 0, 0))
    b.section(4, 4, "Practice", [PRACTICE], parent_cmid=17)

    rated = "".join(
        _item(i, p, "multichoicerated", n, "d>>>>>1####Bad|2####Good")
        for i, p, n in [(61, 1, "The pace was right."), (62, 2, "The labs helped.")]
    )
    free = _item(63, 3, "textarea", "What would you change?", "")
    b.activity(
        SURVEY,
        "feedback",
        "Survey",
        5,
        f"<intro></intro><page_after_submit>{after}</page_after_submit><timeopen>0</timeopen>"
        f"<timeclose>0</timeclose><items>{rated}{free}</items>",
        availability={
            "op": "&",
            "c": [
                {"type": "completion", "cm": EXAM, "e": 1},
                {"type": "completion", "cm": UPLOAD, "e": 1},
            ],
        },
    )
    b.section(5, 2, "Survey", [SURVEY])

    b.write("questions.xml", _questions_xml())
    b.write(
        "gradebook.xml",
        """<gradebook><grade_categories><grade_category id="1"><parent>$@NULL@$</parent>
<fullname>?</fullname><aggregation>13</aggregation></grade_category></grade_categories>
<grade_items><grade_item id="99"><categoryid>$@NULL@$</categoryid><itemtype>course</itemtype>
<gradetype>1</gradetype><grademax>150</grademax><gradepass>0</gradepass></grade_item>
</grade_items></gradebook>""",
    )
    files = "".join(
        f"""<file id="{i}"><contenthash>{h}</contenthash><contextid>1010</contextid>
<component>mod_page</component><filearea>content</filearea><itemid>0</itemid>
<filepath>/</filepath><filename>{n}</filename><filesize>4</filesize>
<mimetype>image/png</mimetype></file>"""
        for i, h, n in [(1, IMAGE_HASH, "diagram 1.png"), (2, MISSING_HASH, "gone.png")]
    )
    b.write("files.xml", f"<files>{files}</files>")
    image_path = dest / "files" / IMAGE_HASH[:2] / IMAGE_HASH
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"\x89PNG")
    b.write("course/course.xml", "<course><summary></summary><visible>1</visible></course>")
    b.finish("Synthetic Linux", "SYN-LNX 01")
    return dest


def pack_mbz(folder: Path, archive: Path) -> Path:
    with tarfile.open(archive, "w:gz") as tf:
        for path in sorted(folder.rglob("*")):
            tf.add(path, arcname=path.relative_to(folder).as_posix(), recursive=False)
    return archive
