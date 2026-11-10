# Agent Skills specification, condensed

The source of truth is [agentskills.io/specification](https://agentskills.io/specification). This is a working summary; if the two disagree, the spec wins.

## Layout

```
skill-name/
├── SKILL.md       required: YAML frontmatter, then Markdown instructions
├── scripts/       optional: code the agent runs
├── references/    optional: docs the agent reads when needed
└── assets/        optional: templates, images, data files
```

Other files and folders are allowed. Refer to them with paths relative to the skill folder, and keep references one level deep from `SKILL.md`.

## Frontmatter fields

These six are the only fields allowed. The reference validator (`skills-ref`) rejects any other top-level key.

| Field | Required | Rules |
|-------|----------|-------|
| `name` | yes | 1-64 characters. Lowercase `a-z`, digits, hyphens. No leading, trailing, or doubled hyphens. Must match the folder name. |
| `description` | yes | 1-1024 characters. Says what the skill does and when to use it, with keywords that help an agent match tasks to it. |
| `license` | no | A license name (`MIT`) or a pointer to a bundled file ("Proprietary. LICENSE.txt has complete terms"). |
| `compatibility` | no | 1-500 characters. Only for real environment needs: target product, system packages, network access. Most skills omit it. |
| `metadata` | no | A map of string keys to string values. Quote anything YAML would read as a number or boolean (`version: "1.0"`). Use distinctive key names. |
| `allowed-tools` | no | Space-separated list of pre-approved tools, e.g. `Bash(git:*) Read`. Experimental; support varies by agent. |

Product-specific keys such as Claude Code's `argument-hint`, `user-invocable`, or `disable-model-invocation` are outside the spec. A skill meant to work across agents should leave them out or move the information into `metadata`.

## Loading budget

Agents load skills in three stages, so put each kind of content where it costs the least:

1. **Metadata**, about 100 tokens: `name` and `description`, loaded at startup for every installed skill.
2. **Instructions**, under about 5,000 tokens: the `SKILL.md` body, loaded when the skill activates. Keep it under 500 lines.
3. **Resources**, as needed: files in `scripts/`, `references/`, and `assets/`, read or run only when the task calls for them. Scripts can run without their source ever entering context.

## Validation

The spec's reference validator:

```sh
skills-ref validate ./my-skill
```

It lives in the [agentskills repository](https://github.com/agentskills/agentskills/tree/main/skills-ref) and is labeled as a demonstration library, so pin a commit if you use it in CI. This skill's `scripts/validate_skill.py` enforces the same rules with no dependencies and adds checks for missing referenced files.
