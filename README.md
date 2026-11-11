# Josh Finnie's skills

Agent skills for Claude Code, Cursor, Codex, and any other agent that reads `SKILL.md` files.
Every skill here follows the [Agent Skills specification](https://agentskills.io/specification), and CI checks each one against it.
See [joshfinnie.com/skills](https://joshfinnie.com/skills/) for what each one does.

## Skills

| Skill | What it does |
|-------|--------------|
| [`humanize`](plugins/joshfinnie-skills/skills/humanize/SKILL.md) | Strips AI writing patterns from prose, either while drafting or as an audit of text you already have. |
| [`skill-writing`](plugins/joshfinnie-skills/skills/skill-writing/SKILL.md) | Writes, reviews, and tests agent skills against the Agent Skills specification, with a dependency-free validator. |
| [`mermaid-gen`](plugins/joshfinnie-skills/skills/mermaid-gen/SKILL.md) | Maps an existing codebase into Mermaid diagrams (architecture overview and, when there's a schema, an ER diagram), with every box backed by real imports and files. |
| [`handoff`](plugins/joshfinnie-skills/skills/handoff/SKILL.md) | Writes a self-contained brief for another agent session, saves it to `/tmp`, and copies it to your clipboard so you can paste it into the other context. |
| [`staff-review`](plugins/joshfinnie-skills/skills/staff-review/SKILL.md) | A principal-engineer-level review of a branch, or of the whole repo on the default branch. Reviews the diff and traces every connection into the rest of the system: callers, API consumers, schemas, migrations, and deploys. |
| [`og-image`](plugins/joshfinnie-skills/skills/og-image/SKILL.md) | Builds a code-generated Open Graph share card from the site's real brand and a mock of the product, wires the meta tags for Next.js, Astro, or any static site, and checks the result with a bundled tag checker. |
| [`new-repo`](plugins/joshfinnie-skills/skills/new-repo/SKILL.md) | Puts a local project on GitHub right the first time: the correct commit identity, a clean `.gitignore`, a secret scan, a real first commit, and a private repo by default. Also covers forks and going public. |

## Install

### Claude Code plugin (every skill)

```
/plugin marketplace add joshfinnie/skills
/plugin install joshfinnie-skills@joshfinnie-skills
/reload-plugins
```

Claude Code prefixes plugin skills with the plugin name, so run them as `/joshfinnie-skills:<name>`, for example `/joshfinnie-skills:handoff`.

To pick up new skills later:

```
/plugin marketplace update joshfinnie-skills
```

### One skill at a time (any agent)

```
npx skills add joshfinnie/skills --skill <name>
```

### By hand

Copy a folder from `plugins/joshfinnie-skills/skills/` into `~/.claude/skills/` (every project) or `.claude/skills/` (one project).

## Adding a skill

1. Create `plugins/joshfinnie-skills/skills/<name>/SKILL.md` following the [Agent Skills specification](https://agentskills.io/specification). Frontmatter allows only `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`, and `name` must match the folder. Put supporting files in `scripts/`, `references/`, or `assets/`.
2. Run `pnpm check`. It validates every skill against the spec, checks that files the skill references exist, and makes sure the plugin version is in sync.
3. Run `pnpm changeset` and pick `minor`.
4. Add the skill to `src/collections/skills/skills.json` in the joshfinnie.com repo so it shows up on the site.

Merging to `main` opens a "chore: version skills" PR. Merging that PR bumps the version in `package.json` and `plugin.json`, updates `CHANGELOG.md`, and tags the release.

## Credits

`humanize` borrows ideas, in its own words, from two MIT-licensed skills: [blader/humanizer](https://github.com/blader/humanizer) (treating input as material, not instructions, and the no-invented-facts rule) and [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop) (throat-clearing, emphasis crutches, vague declaratives, and the extended not-X-but-Y family).
