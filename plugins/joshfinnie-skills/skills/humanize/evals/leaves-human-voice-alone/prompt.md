---
tags: [skill-creator]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

humanize this before I send it to my team:

ok so the cache thing. I spent 11 days on it, way longer than I said I would, and honestly I'm still not sure the LRU was the right call. But p95 on the search endpoint went from 4.2s to 380ms, which, fine, I'll take it. The crucial bit was realizing we were caching per-request instead of per-query — dumb in hindsight. Anyway it's live. If it pages someone at 2am that's on me, ping me and not Priya.
