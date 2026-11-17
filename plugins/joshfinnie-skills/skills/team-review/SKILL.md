---
name: team-review
description: Runs a panel of five specialist code reviewers in parallel on a PR or the current branch, one lens each (correctness and security, readability, fit to purpose, performance, tests), then verifies their serious findings and merges everything into one de-duplicated report with a merge verdict. Use when the user asks for a "team review", a "panel review", "the reviewers", a multi-agent or parallel review, a review "from every angle", or names one of the reviewers (Cathy, Lucy, Percy, Sammy, Tammy). For a single deep principal-engineer pass that traces the change through the whole system, use staff-review instead.
license: MIT
metadata:
  author: Josh Finnie
---

Five reviewers each look at the same change through one lens, so no single pass has to hold every concern at once. Your job as the lead is to set them up with the same context, run them in parallel, check their serious claims yourself, and hand back one short report instead of five long ones.

| Reviewer | Lens | Brief |
|----------|------|-------|
| Correctness Cathy | Bugs, edge cases, concurrency, auth, security, error handling | [references/correctness-cathy.md](references/correctness-cathy.md) |
| Legible Lucy | Readability, naming, structure, project conventions | [references/legible-lucy.md](references/legible-lucy.md) |
| Pragmatic Percy | Does it do what it set out to do, scope, architecture, docs | [references/pragmatic-percy.md](references/pragmatic-percy.md) |
| Speedy Sammy | Performance at realistic scale | [references/speedy-sammy.md](references/speedy-sammy.md) |
| Testy Tammy | Tests and evidence the change works | [references/testy-tammy.md](references/testy-tammy.md) |

Where lenses could overlap, each concern has one owner so it isn't reported twice: Cathy owns auth and security, Lucy owns duplicated code, Percy owns architecture, env and deploy config, and missing docs, and Tammy owns missing tests. The lens applies to questions as well as findings: a reviewer that wonders about something outside its lens leaves it to the owner.

This is a review, not a rewrite. Neither you nor the reviewers edit, commit, push, or check out anything.

## 1. Pin down the change

Work out what is under review before dispatching anyone, so all five look at the same thing.

- **A PR number or URL**: the change is `gh pr diff <pr>`, and the context is `gh pr view <pr>`.
- **Nothing named**: the current branch against its merge base with the default branch, plus uncommitted work. Find the default branch with `git symbolic-ref --short refs/remotes/origin/HEAD` (fall back to `main`, then `master`), then use `git diff <default>...HEAD` and `git diff HEAD`.
- **A branch, commit range, or path**: use it as given.

If the diff is empty, stop and say so. Don't review the whole repo by accident.

## 2. Gather shared context once

Collect what every reviewer needs, so five agents don't each rediscover it:

- The exact command(s) that produce the diff, and the list of changed files.
- The stated goal: the user's words, the PR title and body, a ticket ID in the branch name or commits, and the commit messages.
- The project's own rules: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, any project skills (`.claude/skills/*/SKILL.md` or similar) for the areas touched, and the lint, type-check, test, and build commands from the package manifest, `Makefile`, or CI config.
- What kind of project this is (public web app, internal tool, library, CLI, service) and its stack, because that decides what counts as slow, risky, or conventional.

**Large diffs.** Past roughly 1,000 changed lines or 30 files, not counting lockfiles and generated code, five full reads get expensive and shallow. Give each reviewer a focus list instead of the whole diff. Percy still gets every file, because judging scope needs the whole picture. Tammy gets the tests plus the code they cover. Sammy gets the hot paths, queries, and client code, but not docs, tests, or config. Cathy and Lucy get the source files. Say in the dispatch that the list is a focus, not a fence: a reviewer can open any other file it needs. Always leave lockfiles and generated files out of everyone's list.

## 3. Dispatch all five in parallel

Start the five reviewers at the same time, one subagent each, in a single turn. In Claude Code that means five Agent tool calls in one message. Give each one:

1. The path to its brief from the table above (resolve it to an absolute path), with the instruction to read it first and follow it.
2. The shared context from step 2, plus its focus list if the diff is large.
3. The ownership map above, and the rule that questions stay in lens too.
4. The read-only rule: no edits, commits, pushes, checkouts, installs, or browser downloads, and never point tests or scripts at production. Read `.env` files and credential stores only if the project's rules say it's safe.

Don't pass your own suspicions along. A reviewer handed a hypothesis tends to confirm it, and the point of five lenses is five independent reads.

If the agent you're running in can't start subagents, run the five passes yourself one after another, re-reading each brief before its pass and keeping its findings separate until step 5.

## 4. Verify the serious findings

Reviewers misread code with the same confidence they read it correctly. Before reporting any Critical or Major finding, open the cited `file:line` yourself and try to disprove it: check whether a caller already guards the case, whether the code path is reachable, and whether the config really says what the reviewer claims. Run a cheap command (type check, lint, a single test) when it settles the question.

Do the same for open questions. Reviewers can't download anything, so they often leave a question a single read-only check would settle, such as an asset's real dimensions, a config value, or whether a route exists. When a question would change a finding and a cheap read-only check answers it, run the check and fold the answer in rather than passing the question along.

Drop findings that don't hold up, downgrade ones that are real but overstated, and keep a count of both. Minor findings and nits pass through unverified, but discard any that contradict the project's own rules.

## 5. Write one report

Merge, don't concatenate. When two reviewers flag the same line, keep one entry and tag both. Use this shape:

```markdown
## Team review: <PR title or branch>

**Verdict (Percy):** Yes with gaps. <one sentence on whether it does what it set out to do>

### Critical
- `src/api/orders.ts:42` (Cathy) The refund handler skips the auth check when `orderId` is numeric, so any signed-out user can refund an order. Move the `requireUser()` call above the branch.

### Major
- ...

### Minor and nits
- ...

### Questions
- <intent only a human can confirm>

Checked: <commands run, by reviewer>. Dropped <n> findings that didn't hold up, downgraded <n>.

**Bottom line:** merge with fixes.
```

Leave out empty severity sections. Each finding gets its `file:line`, the reviewer tag, the problem with the input or scenario that triggers it, and a concrete fix. The bottom line is one of: good to merge, merge with fixes, or needs work.

Keep it proportionate. A small, clean change gets a verdict, a line saying what the reviewers checked, and "good to merge". Padding a report with invented concerns teaches people to skip reviews.
