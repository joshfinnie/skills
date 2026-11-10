# Audit report format

Use this structure when the task is to *report* findings rather than rewrite in place (e.g. "check this for AI-isms" as opposed to "fix this").

**Summary**: total instances found, breakdown by category.

**Findings**, one entry per instance, in the order they appear in the text:
- **Location**: line number, paragraph number, or a short locating quote
- **Category**: transition / buzzword / opener / hype / hedge / rhythm / structure
- **Quoted text**: the exact phrase or sentence
- **Fix**: a specific replacement, or an instruction ("cut," "rewrite as a direct statement," "vary sentence length here")

**Rhythm findings** quote the first and last sentence of the flat run, give the word counts from `scripts/rhythm.py`, and name the move: merge, split, cut, or extend.

**Patterns**: after the per-instance list, name anything systemic. If a transition word recurs a dozen times, or every section opens with a definition, say so once rather than burying it in twelve separate findings. Patterns are more actionable than instance counts.

Don't flag: quoted or attributed speech (someone else's actual words), proper nouns, or a construction the piece's own style guide explicitly endorses. Don't flag isolated Tier 3 words, a single em dash, or one instance of anything that only becomes a problem as a cluster (see Guardrails in SKILL.md).

## Optional: a rough severity score

If the user wants a quick read on how AI-flavored a piece is (not a formal metric, just a gut-check label), use:

| Findings density | Label |
|:--|:--|
| 0-1 per 500 words | Clean |
| 2-4 per 500 words | Minor tells, easy cleanup |
| 5-9 per 500 words | Mixed, reads like partial AI editing |
| 10+ per 500 words, or 3+ structural tells | Heavy AI smell |

Treat this as a signal for prioritizing fixes, not a verdict. A model scoring its own rewrite in the same pass tends to grade generously.
