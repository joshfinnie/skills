---
name: handoff
description: Writes a self-contained handoff document for another agent session (for example, from the API repo's session to the frontend's), saves it to /tmp, and copies it to the clipboard so the user can paste it straight into the other session. Use whenever the user says "handoff", "hand this off", "write this up for the frontend/backend/other session", "brief the other agent", "summarize what the API side needs to know", or wants context from this session carried into another one.
license: MIT
metadata:
  author: Josh Finnie
---

The reader is another agent in a different session, often in a different repo. It has none of this conversation and can't ask follow-up questions before it starts working, so the document has to carry everything it needs to act correctly. Write for that reader.

## 1. Figure out the direction

Work out who the handoff is for and what they need to do. The user's words usually say it ("/handoff for the frontend: the new pagination params"). If they don't, infer it from the session: an API change usually goes to the client side, and a client need usually goes to the API side. Ask only if both directions are plausible.

Then gather facts from this session and the repo, not from memory:

- what changed, with file paths, and the branch and latest commit (`git rev-parse --abbrev-ref HEAD`, `git log -1 --format='%h %s'`)
- the exact interface the other side touches: routes, methods, request and response bodies, types, status codes, error shapes, event names, env var names
- anything decided along the way that the other side would otherwise get wrong

## 2. Write the document

Use this structure. Drop sections that would be empty rather than writing "none."

```markdown
# Handoff: <short title>

From: <this side, e.g. "API session (picsky api repo)">
To: <the other side, e.g. "frontend session (web/)">
Branch / commit: <branch> @ <sha> "<subject>"

## What you need to do
1-5 concrete tasks for the reader, in order.

## What changed on this side
Short bullets with file paths. Only what affects the reader.

## Contract
Exact routes, payloads, types, and errors. Copy real shapes from the code.

## Decisions and gotchas
Things decided here that the reader must not undo or guess differently.

## Open questions
Anything unresolved, and who should answer it.

## Verify
Commands or requests the reader can run to confirm it works end to end.
```

Writing rules, and why they matter:

- **Copy, don't paraphrase, anything the reader will code against.** Field names, casing, nullability, and status codes must match the source exactly, because the reader will type them in literally. Pull them from the code or a real response, not from memory.
- **Paths are relative to this repo** and labeled as such ("in the API repo: `internal/handler/photos.go`"). The reader's working directory is somewhere else.
- **Never include secret values.** Name env vars and say where the value lives, but don't paste tokens, keys, passwords, or connection strings, since the file sits in a shared temp directory and on the clipboard.
- **Say what's not done.** If the API side still has a TODO that the frontend will hit, put it in "What you need to do" or "Open questions" instead of leaving it for the reader to discover.
- **Keep it short enough to paste.** Aim for under about 150 lines. Link to a file in the repo for anything longer rather than inlining it.

## 3. Save and copy

Pipe the finished document to `scripts/handoff.py` (relative to this skill's folder) with a short name:

```sh
python3 scripts/handoff.py --name api-pagination <<'EOF'
# Handoff: ...
EOF
```

It writes `/tmp/handoff-<name>-<timestamp>.md`, refreshes `/tmp/handoff-latest.md`, and copies the document to the clipboard using pbcopy, clip.exe (WSL), wl-copy, xclip, or xsel, whichever exists. Pass `--dir` to save somewhere else or `--no-clipboard` to skip the copy.

## 4. Tell the user

Reply with the saved path, whether it's on the clipboard (the script's last line says), and a one-line summary of what the handoff asks the other side to do. If the clipboard copy failed, tell them to open the file and copy it, or to point the other session at `/tmp/handoff-latest.md`, which works when both sessions run on the same machine.
