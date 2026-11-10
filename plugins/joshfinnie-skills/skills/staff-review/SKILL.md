---
name: staff-review
description: A thorough, staff/principal-engineer-level code review of a git branch, or of the whole codebase when run on the default branch. Reviews the changed code line by line and also follows every connection into the rest of the system (callers, API consumers, frontends, schemas, migrations, config, deploys) to find what the diff breaks outside itself. Use whenever the user asks to review a branch, PR, or their changes, wants a "staff-level", "principal", "senior", "thorough", or "holistic" review, asks "is this ready to merge", or asks for a review of the whole repo or codebase.
license: MIT
metadata:
  author: Josh Finnie
---

Review the way a principal engineer who owns the whole system would. The diff is where the review starts, not where it ends: the bugs that cost the most usually live in code the branch didn't touch but now behaves differently against. Your job is to find those, rank everything by what it would cost the team, and say plainly whether this should merge.

This is a review, not a rewrite. Don't edit, commit, push, or check out anything. Running tests, type checks, linters, and builds to confirm a finding is good practice; installing new tools or downloading browsers to do it is not, so say what you couldn't run instead.

## 1. Pick the mode and gather context

Run `scripts/branch_context.py` (paths here are relative to this skill's folder) from the repository root:

```sh
python3 scripts/branch_context.py --repo /path/to/repo
```

- **Branch mode**, on any branch other than the default: compares against the merge base with the default branch. Pass `--base <ref>` to compare against something else, or when the user names a branch, PR, or range.
- **Whole-repo mode**, on the default branch or with `--whole-repo`: there's no diff, so the script maps the codebase instead (modules, test coverage by module, hotspots, largest files, TODO markers, CI and deploy config).

Read its output before anything else. In branch mode it lists the files outside the diff that reference changed symbols, the code still using renamed fields or dropped columns, and the interfaces the diff touches. Each of those is a lead you must follow up in step 3.

## 2. Understand the intent

Before judging the code, work out what it's for. Read the commit messages, the PR description if there is one (`gh pr view` when the GitHub CLI is available), any linked issue, and the README sections the change relates to. Write the intent down in one or two sentences of your own. Every finding is measured against it, and a branch that does the wrong thing well still fails.

In whole-repo mode, the intent is the system itself: read the README, entry points, and deploy config until you can say what the system does and how it runs.

## 3. Read everything, then follow every connection

**In branch mode:**

1. Read each changed file in full, not just the hunks. A hunk that looks right can contradict code twenty lines above it.
2. Read the changed tests and ask what they actually prove. A test that passes on a broken implementation proves nothing.
3. Follow every lead from the script: each caller of a changed function, each file still using a renamed field or dropped column, each importer of a changed module. Open them and decide whether they still work.
4. Then hunt for the connections no script can see:
   - **Consumers across a process boundary**: frontends, mobile apps, other services, OpenAPI specs, SDKs, webhooks, and anything that parses this code's output.
   - **Data already in production**: rows written by the old code, cached values, queued jobs, and clients still running the old version during a deploy.
   - **How things actually run**: how migrations get applied (once and tracked, or re-run on every boot?), the deploy order of database and app, cron jobs, background workers, and feature flags.
   - **Configuration**: env vars per environment, defaults, and secrets.

**In whole-repo mode**, you can't read everything in a large codebase, so be deliberate about it. Start with the entry points and the request path through the system, then the churn hotspots and the largest files, then the modules with no tests, then anything touching auth, money, or user data. Say in the report which areas you covered and which you didn't.

## 4. Review through every lens

Work through [references/checklist.md](references/checklist.md). It covers correctness, system connections, security, data and migrations, performance, reliability and operability, tests, and design. Not every lens applies to every change, but decide that deliberately rather than by skipping it.

Run what's cheap and relevant: the test suite for the touched packages, the type checker, the linter, the build. A finding confirmed by a failing command is worth ten argued from reading.

## 5. Verify before you report

Each finding needs a `file:line`, the concrete scenario that triggers it, and what happens to a user or to the system when it does. Try to disprove your own finding first: check whether a caller already guards against it, whether the column really is gone, whether the test really runs. If you can't confirm something but it would matter if true, report it as a question, not a defect. A review that cries wolf trains people to skip reviews.

## 6. Write the review

Use the structure in [references/report-format.md](references/report-format.md): verdict, what the branch does, system impact, findings by severity, test gaps, questions, and what's good. Save it to `/tmp/staff-review-<repo>-<branch>.md` and give the full review in your reply.

How to sound like the staff engineer in the room:

- **Lead with what matters.** Blockers first, each with its consequence in one sentence. Nobody should have to read past nits to learn the deploy will crash.
- **Explain the why.** "This renames `user_id` to `owner_id`, but the nightly export in `jobs/export.py` still selects `user_id`, so tonight's export fails" teaches something. "Migration looks risky" doesn't.
- **Propose the fix**, with a short code sketch when it helps. If there are two reasonable fixes, say which you'd pick and why.
- **Separate defects from taste.** Mark preferences as such ("I'd lean toward..."), and cap nits at about five. If there are more, note the pattern once.
- **Call out the good parts, specifically.** "The retry wrapper reuses the backoff helper in `lib/http.ts` instead of adding a second one" is useful. "Nice work!" isn't.
- **Don't inflate.** If the branch is solid, say so and keep the review short. Inventing findings to look thorough is its own kind of failure.
