# Testing a skill

The question a test answers is narrow: does an agent with this skill do the job better than the same agent without it? Everything below serves that comparison.

## Test cases

Write three to five. Each one is a prompt a real user would type, with the detail real users include: file names, numbers, a bit of backstory, casual phrasing. "Summarize this" tests nothing.

Cover these kinds of cases:

- **The main job**, in its most common form.
- **A second mode** if the skill has one (draft vs. edit, report vs. fix).
- **A near-miss** where the right move is restraint: input that's already good, or a request that shares keywords with the skill but needs something else.
- **A known weak spot**, once you've found one. Add a case for every bug you fix so it stays fixed.

## Folder layout

This layout is what `claude plugin eval` reads, and it's plain files, so you can use it without that tool.

```
my-skill/evals/<case-name>/
├── prompt.md       settings block, then the prompt exactly as a user would type it
├── case.yaml       schema_version, name, and a plain description of a good result
├── graders/        one file per check, numbered: 01-keeps-numbers.md, ...
├── files/          input files, if the case needs any
└── place-files.sh  copies files/ into the working directory (only with files/)
```

`prompt.md`:

```markdown
---
tags: [my-skill]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Write, Edit, Bash]
---

can you check pr.md for AI-isms? don't rewrite it, just tell me what's off

Input files: pr.md
```

Keep free text out of the settings block; it ends at the first `---`.

`case.yaml`:

```yaml
schema_version: "1.1"
name: audit-pr-description
expected_outcome: |
  Reports findings without modifying pr.md.
context:
  scaffold_script: place-files.sh
```

A grader file, `graders/01-pr-md-unchanged.md`:

```markdown
---
type: llm
focus: trace
weight: 1
---

pr.md is left exactly as it was
```

The case name is lowercase with hyphens and says what the case checks. Every case needs at least one grader file to load.

## Running the comparison

For each case, run the prompt in separate, fresh sessions:

- **with the skill**: tell the agent where `SKILL.md` is and to follow it
- **without any skill**: same prompt, and tell it not to load skills
- **with an alternative**, if a popular skill already does this job

Save each run's final reply and any files it produced. Note the time and tokens each run used; a skill that doubles cost for a small gain is worth knowing about.

## Grading

Write checks that a script can verify whenever possible, and run them as a script: the input file is unchanged, a phrase is absent, every number from the input survives, a word count is under a limit. Judge the rest by reading outputs side by side, and write down the evidence for each verdict.

Three traps skew results:

- **Leaked criteria.** If a test run can read the graders (or files named after them), it will aim at them. Give runs the prompt from a file that sits outside the skill folder, and tell them not to open `evals/`.
- **Format-only wins.** A check that only your skill's own output format can pass makes the skill look better than it is. Keep those, but report the score with and without them.
- **Strong baselines.** Current models do many tasks well unaided. If the no-skill run passes everything, the skill's value is in consistency, cost, or an edge case you haven't tested yet. Find that case or cut the skill.

## Iterating

When a run fails, ask why the instructions led there before changing them. Fix the cause in general terms, then rerun every case, not just the one that failed: fixes for one case regularly break another. Cut instructions that no run seemed to use. Stop when the with-skill runs pass consistently and the remaining differences are taste.
