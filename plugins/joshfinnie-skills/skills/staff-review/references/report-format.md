# Report format

Use this structure. Leave out a section that would be empty, except the verdict.

```markdown
# Review: <branch> (<repo>)

**Verdict:** Request changes | Approve with changes | Approve
<One or two sentences: the deciding reasons.>

## What this branch does
<The intent in your own words, then how the change carries it out. If the
author's description and the code disagree, say so here.>

## System impact
<What outside the diff is affected and how: callers, consumers, data, deploys.
List the connections you checked, including the ones that turned out fine, so
the author knows they were considered. A small Mermaid flowchart helps when
the change crosses several components; skip it otherwise.>

## Findings

### Blockers
Must be fixed before merge: broken behavior, data loss, security holes,
failed deploys.

#### 1. <Short title>
`path/to/file.ext:123`
<What's wrong, the concrete scenario that triggers it, and what happens.>
<Evidence: the code, a command you ran and its output, or the other file
that breaks.>
**Fix:** <What to do, with a short sketch when it helps.>

### Major
Should be fixed in this branch: real bugs in edge cases, missing auth checks
on low-risk paths, missing tests for the main behavior, rollout hazards.

### Minor
Worth fixing, fine as a follow-up: small bugs with little impact, unclear
code, missing logs.

### Nits
Style and taste, five at most. Mark preferences as preferences.

## Tests
<What the tests cover, what they miss, and whether you ran them (with the
result). If you couldn't run them, say why.>

## Questions for the author
<Things you couldn't confirm that would matter if true.>

## What's good
<Specific things done well, with file references.>

## Coverage
<What you read and ran. In a whole-repo review, which areas you covered in
depth and which you only skimmed or skipped.>
```

## Severity, decided by cost

| Severity | Use when | Verdict impact |
|----------|----------|----------------|
| Blocker | Merging causes an outage, data loss, a security hole, or a broken deploy, or the change doesn't do what it's for | Request changes |
| Major | A real bug or risk that users or operators will hit, but not catastrophic | Approve with changes, or request changes if there are several |
| Minor | Small impact, or only maintainability | Approve |
| Nit | Taste | Approve |
| Question | Unconfirmed, but would be a blocker or major if true | Depends on the answer |

Number findings across the whole review (1, 2, 3...) so the author can reply "fixed 1 and 3, disagree on 2."

## Whole-repo variant

Replace "What this branch does" with **What the system does** (purpose, how it runs, main components), and "System impact" with **Architecture**: the components and how they depend on each other, plus where that structure helps or hurts. Group findings by severity as usual, and add a **Recommendations** section with the three to five changes that would most improve the codebase, in priority order.
