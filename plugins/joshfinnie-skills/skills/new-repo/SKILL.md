---
name: new-repo
description: Puts a local project on GitHub correctly the first time. Picks the right commit identity before the first commit (so a personal project doesn't ship with a work email, or the reverse), fixes .gitignore, scans staged files for secrets, writes a real first commit on main, creates the repository with the gh CLI (private by default), pushes, and verifies. Also covers forks (keeping upstream) and the checks to run before making a private repo public. Use whenever the user says "create a repo", "make a private repo", "put this on GitHub", "push this to a new repo", "init and push", or "make this repo public". Not for cloning existing repos or opening pull requests.
license: MIT
compatibility: Requires git and an authenticated GitHub CLI (gh).
metadata:
  author: Josh Finnie
---

Creating a repo looks like three commands, but the mistakes are expensive to undo once pushed: commits under the wrong email, a `.env` file in history, or a public repo that should have been private. This skill front-loads those decisions so the first push is the right one.

## Defaults

Use these unless the user or their agent instructions (CLAUDE.md, AGENTS.md, or similar) say otherwise. Instructions always win.

| Setting | Default |
|---|---|
| Owner | The authenticated user: `gh api user --jq .login`. Use an org only when the user names one. |
| Visibility | Private. Public only when asked. |
| Name | The directory name, unchanged. |
| Default branch | `main` |
| Commit trailers | None added by the agent, such as co-author lines, unless the user's instructions ask for them. |

## 1. Look before touching anything

```sh
git status -sb 2>&1; git remote -v; git log --oneline -3 2>&1
gh auth status 2>&1 | head -4
gh repo view <owner>/<name> 2>&1 | head -2
```

If a GitHub repo with that name already exists, stop and ask. Never push over it. If the folder already has an `origin` remote, ask what it is before replacing it.

## 2. Create the remote first

```sh
git init -q -b main                     # skip if already a repo; use `git branch -M main` to rename
gh repo create <owner>/<name> --private --description "<one line from the README or package description>"
git remote add origin git@github.com:<owner>/<name>.git   # or https, matching `gh config get git_protocol`
```

Creating the empty repo before the first commit means git rules keyed on the remote URL (`includeIf "hasconfig:remote.*.url:..."`) are already active when the identity is checked in the next step.

## 3. Settle the commit identity

The goal is that every commit carries the identity the user would choose for this repo. Check, in order:

1. **The user's instructions.** If they state an identity rule ("personal repos use me@example.com, repos under `acme-corp` use my work address"), apply it and set it locally: `git config --local user.name "..."` and `git config --local user.email "..."`.
2. **What git resolves now:** `git config user.name; git config user.email; git config --show-origin user.email`.
3. **A sanity check.** Compare the resolved email with the owner. A company-domain address on a repo owned by a personal account, or a personal address on a company org's repo, is usually a mistake inherited from the global config. When that mismatch shows up and nothing in the instructions settles it, ask once, naming both the email and the owner.

When the user answers, set the identity locally for this repo. Then mention that the rule could live permanently in their instructions file or in a git `includeIf` block, so the question doesn't come up again. Don't edit their global git config without a yes.

If local commits already exist under the wrong identity and nothing has been pushed, fix them now. That's cheap before the push and painful after it:

```sh
git rebase -r --root --exec 'git commit --amend --no-edit --reset-author'
```

Only rewrite commits the user authored. Leave other people's commits alone, which matters most in forks.

## 4. Fix .gitignore before staging

Cover whatever applies to the stack: dependency folders (`node_modules/`, `.venv/`, `vendor/`), build output (`dist/`, `build/`, `.next/`, `target/`), env files (`.env`, `.env.*`, with `!.env.example` kept), local tool state (`.netlify/`, `.vercel/`, `.terraform/`), logs, coverage output, and OS files (`.DS_Store`). Also look for large downloaded binaries that tooling fetches on its own. If something that should be ignored is already tracked, untrack it with `git rm -r --cached <path>`.

## 5. Stage, then scan for secrets

```sh
git add -A
git diff --cached --name-only | rg -i '(^|/)\.env($|\.)|\.pem$|\.key$|\.p12$|credentials|secret' | rg -v '\.env\.example$'
git diff --cached | rg -n 'postgres(ql)?://[^:\s]+:[^@\s]+@|mysql://[^:\s]+:[^@\s]+@|mongodb(\+srv)?://[^:\s]+:[^@\s]+@|AKIA[0-9A-Z]{16}|sk_(live|test)_[A-Za-z0-9]{10,}|rk_(live|test)_|whsec_[A-Za-z0-9]{10,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[abp]-|AIza[0-9A-Za-z_-]{35}|BEGIN [A-Z ]*PRIVATE KEY'
```

Any hit stops the flow. Unstage the file, move the value into an ignored env file, and tell the user which file and line matched. Never print the secret itself. If `rg` isn't installed, use `grep -nE` with the same patterns.

## 6. First commit and push

Write a commit message that says what the project is and what's in it: a short subject and a few body lines. "Initial commit" tells a future reader nothing. Follow the project's commit convention if it has one.

```sh
git commit -q -F <message-file>
git push -u origin main
```

## 7. Verify and report

```sh
gh repo view <owner>/<name> --json url,visibility,defaultBranchRef --jq '"\(.url) \(.visibility) \(.defaultBranchRef.name)"'
git log -1 --format='%h %an <%ae>'
git status -sb | head -1
```

Report the URL, the visibility, the identity on the commit, and that `main` tracks `origin/main` with nothing ahead.

## Forks

When the project started as a clone of someone else's repo:

- Keep the original as `upstream` (`git remote rename origin upstream`), then create the user's repo and add it as `origin`.
- Rewrite nothing in the upstream history. Only the user's new commits get the user's identity.
- Say it's a fork in the description, for example "(fork of someone/project)".

## Making a private repo public

Run these checks first, report what they find, and wait for a clear yes:

1. **Secrets anywhere in history**, not just the working tree. Run the content pattern from step 5 over `git log -p --all`. List every path ever committed with `git log --all --name-only --format= | sort -u` and look for env files, keys, and dumps.
2. **Authorship.** `git log --all --format='%an <%ae>' | sort | uniq -c`. Point out addresses the user may not want public, like a work email on a personal project.
3. **Content.** README, LICENSE (a public repo without one isn't open source), internal notes and plans, hardcoded internal URLs, and customer data in fixtures or seeds.

Then run `gh repo edit <owner>/<name> --visibility public --accept-visibility-change-consequences`.

If a secret ever reached history, the fix is to rotate it. Rewriting history doesn't help once anyone could have cloned the repo, so say that plainly instead of offering a history rewrite as the fix.

## Out of scope

Hosting, databases, CI, and environment setup are separate jobs. Suggest them as next steps when the project clearly needs them, but don't start them here.
