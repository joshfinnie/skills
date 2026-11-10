# joshfinnie-skills

## 0.1.0

### Minor Changes

- [`6fa412c`](https://github.com/joshfinnie/skills/commit/6fa412c825983e682a46680a4e09aa924d314eda) Thanks [@joshfinnie](https://github.com/joshfinnie)! - Add `handoff`, which writes a self-contained brief for another agent session, saves it to `/tmp`, and copies it to the clipboard on macOS, Linux, and WSL.

- [`6fa412c`](https://github.com/joshfinnie/skills/commit/6fa412c825983e682a46680a4e09aa924d314eda) Thanks [@joshfinnie](https://github.com/joshfinnie)! - Add `humanize`, a skill that strips AI writing patterns from prose while drafting or as an audit of existing text, with `rhythm.py` for measuring sentence-length variety.

- [`6fa412c`](https://github.com/joshfinnie/skills/commit/6fa412c825983e682a46680a4e09aa924d314eda) Thanks [@joshfinnie](https://github.com/joshfinnie)! - Add `mermaid-gen`, which surveys a codebase (layout, entry points, schema files, and the real import graph) and writes architecture and ER diagrams to Markdown, with a linter that catches Mermaid syntax that won't render.

- [`6fa412c`](https://github.com/joshfinnie/skills/commit/6fa412c825983e682a46680a4e09aa924d314eda) Thanks [@joshfinnie](https://github.com/joshfinnie)! - Add `skill-writing`, a skill for writing, validating, and testing agent skills against the Agent Skills specification. Its `validate_skill.py` now validates every skill in this repo.

- [`6fa412c`](https://github.com/joshfinnie/skills/commit/6fa412c825983e682a46680a4e09aa924d314eda) Thanks [@joshfinnie](https://github.com/joshfinnie)! - Add `staff-review`, a staff-level review of a branch (or the whole repo on the default branch) that follows changed code into its callers, consumers, schemas, and deploys. Its `branch_context.py` maps the blast radius, including renamed serialized fields and dropped columns still used outside the diff.
