# Course Study Skills

Four coordinated [Codex](https://developers.openai.com/codex/skills) skills for course self-study and exam preparation.

The bundle is designed for learning from lecture notes, slides, handwritten notes, prescribed texts, teacher exercises, past papers, marking schemes, and revision materials. It keeps one course plan and separates teaching, evidence-based exam analysis, and question design so that these responsibilities do not conflict.

## Included skills

| Skill | Use it for |
| --- | --- |
| `study-planner` | Main entry point: continue a course, select the next lesson or practice, and maintain a flexible, exam-aware plan with saved evidence. |
| `course-study` | Coherent university-style lessons, local prerequisite repair, and temporary concept or question help. |
| `exam-analysis` | Traceable analysis of course requirements, past papers, marking schemes, question types, and topic statistics. |
| `practice-builder` | Teacher- and past-paper-grounded exercises, variants, complete solutions, and checking notes. |

`study-planner` is the normal entry point. The other three skills can also be invoked directly for a focused task.

## Install

Install all four folders together: their documentation uses relative links to the shared planning skill.

```bash
git clone https://github.com/tony-creat06/course-study-skills.git
cd course-study-skills
cp -R skills/study-planner skills/course-study skills/exam-analysis skills/practice-builder ~/.codex/skills/
```

Alternatively, Codex's built-in Skill Installer can install the folders individually from GitHub. Use the paths `skills/study-planner`, `skills/course-study`, `skills/exam-analysis`, and `skills/practice-builder` from this repository. Restart Codex if the new skills do not appear automatically.

If a destination skill already exists, back it up first instead of overwriting it blindly.

## Start studying

For an existing course with saved records:

```text
$study-planner 继续学习课程 X，读取已有课程记录并安排下一段。
```

For a new course, state the course identity, where its materials are, and where you want the separate learning records saved:

```text
$study-planner 我想从零学习课程 X。资料在 <path>；请把学习记录保存到 <path>。
```

The skills treat learner-provided materials as the primary source. Recent two to three years of past papers are the highest-priority evidence for exam style; teacher exercises establish course emphasis; older papers are secondary. AI-authored variants and new questions supplement the limited supply of original questions, and are explicitly labelled as such.

## What is included and excluded

This repository contains only the reusable skill instructions and their small standard-library Python helpers. It does not contain lecture notes, past papers, answers, personal progress, student work, or other course materials.

This is version 0.2.5. It adds scoped preference updates: temporary requests, continuing user preferences, tentative observations, and learning outcomes are recorded separately. The main planner maintains personal records; teaching adapts within the current request and course requirements. A single reaction does not establish a permanent learning style. It retains the v0.2.4 feedback, practice and resume guidance, plus the mathematical text checks and separate assistance/outcome review fields. Legacy review inputs remain readable. The four responsibilities and normal final course depth are preserved.

Personalization uses local course records, not automatic rewriting of the shared skill source. Preferences can change or be withdrawn. Cross-course reuse requires the same learner and explicitly general preferences from designated records; personal records are not published with this bundle.

Helper regressions and bounded simulated use check software and workflow behavior. They do not establish superior learning, long-term retention, or exam results compared with direct-file tutoring. Important course-specific content still needs checking against the teaching materials.

## Development checks

Run `python3 -B -m unittest discover -s tests -v` for helper regressions. Mathematical note checks are read-only:

```bash
python3 skills/course-study/scripts/check_math.py <saved-lesson.md>
```

The text checker flags common delimiter, brace, and command-escaping mistakes. It does not render formulas or verify their meaning; inspect warnings in context. Test data in this repository is synthetic and contains no learner records or course PDFs.

## Design references

The workflow adapts specific ideas from [Revision Tutor](https://github.com/yangcodingmaster/Revision-Tutor/blob/main/SKILL.en.md) (local reasoning gaps), [OpenTutor](https://github.com/LEARNableLabs/opentutor/blob/main/docs/methodology.md) (concrete revisit and variation tasks), and [DeepTutor](https://arxiv.org/html/2604.26962v3) (source grounding and separate tutoring/practice evaluation). These inform the design; their reported evaluations do not validate this bundle. Coherent lectures, optional in-class checks, and most practice after class remain the defaults.

The [IES study guide](https://ies.ed.gov/ncee/wwc/practiceguide/1) informs the combination of worked examples and problem solving. [Carnegie Mellon's learning principles](https://www.cmu.edu/teaching/principles/learning.html) inform targeted feedback and practice that integrates skills and requires choosing when to apply them. These are design grounds, not evidence that this bundle improves an individual student's outcomes.

The [learning-styles evidence review](https://journals.sagepub.com/doi/10.1111/j.1539-6053.2009.01038.x) informs the distinction between expressed presentation preferences and evidence that a matching teaching method improves learning. Preference updates do not assign fixed learner types or establish effectiveness by themselves.

## License

MIT. See [LICENSE](LICENSE).
