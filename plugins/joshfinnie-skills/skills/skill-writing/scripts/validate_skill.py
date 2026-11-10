#!/usr/bin/env python3
"""Validate skill folders against the Agent Skills specification.

Usage:
    python3 validate_skill.py SKILL_DIR [SKILL_DIR ...]

Spec: https://agentskills.io/specification

Errors (exit 1):
  - SKILL.md missing, or no YAML frontmatter between --- lines
  - frontmatter fields other than name, description, license, compatibility,
    metadata, allowed-tools
  - name not 1-64 chars of a-z, 0-9 and single hyphens, or not matching the folder
  - description empty or over 1024 characters
  - compatibility over 500 characters
  - metadata values that aren't strings
  - SKILL.md over 500 lines
  - a relative link, or a scripts/, references/ or assets/ path, in SKILL.md
    that doesn't exist

Warnings (exit 0):
  - description under 80 characters or with no "use when"-style trigger
  - a references/ file over 300 lines with no table of contents
  - a scripts/ file that isn't executable

Standard library only. The frontmatter parser handles the subset of YAML the
spec needs (scalars, quoted strings, | and > blocks, one nested map).
"""

import os
import re
import sys

ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_LINES = 500
TRIGGER = re.compile(r"\b(use (it |this )?(when|whenever|for|to)|triggers? on|when the user)\b", re.I)


class FrontmatterError(Exception):
    pass


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace("''", "'") if value[0] == "'" else bytes(inner, "utf-8").decode("unicode_escape")
    if value.startswith(("[", "{", "&", "*", "!")):
        raise FrontmatterError(f"unsupported YAML value {value!r}; use a plain or quoted string")
    return re.sub(r"\s+#.*$", "", value)


def parse_frontmatter(text):
    lines = text.splitlines()
    result, i = {}, 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0].isspace():
            raise FrontmatterError(f"unexpected indentation on line {i + 1}: {line.strip()!r}")
        match = re.match(r"^([A-Za-z0-9_-]+):(.*)$", line)
        if not match:
            raise FrontmatterError(f"can't parse line {i + 1}: {line!r}")
        key, rest = match.group(1), match.group(2).strip()
        i += 1
        if rest in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace()):
                block.append(lines[i].strip())
                i += 1
            joined = "\n".join(block).strip() if rest.startswith("|") else " ".join(b for b in block if b)
            result[key] = joined
        elif rest == "":
            nested = {}
            while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace()):
                if lines[i].strip():
                    sub = re.match(r"^\s+([A-Za-z0-9_.-]+):(.*)$", lines[i])
                    if not sub:
                        raise FrontmatterError(f"can't parse nested line {i + 1}: {lines[i].strip()!r}")
                    raw = sub.group(2).strip()
                    is_string = raw[:1] in "\"'" or not re.fullmatch(r"-?\d+(\.\d+)?|true|false|null|~", raw)
                    nested[sub.group(1)] = unquote(raw) if is_string else ("__nonstring__", raw)
                i += 1
            result[key] = nested
        else:
            result[key] = unquote(rest)
    return result


def check(skill_dir):
    errors, warnings = [], []
    skill_dir = os.path.normpath(skill_dir)
    folder = os.path.basename(skill_dir)
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return [f"no SKILL.md in {skill_dir}"], warnings

    with open(skill_md, encoding="utf-8") as handle:
        source = handle.read()
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", source, re.S)
    if not match:
        return ["SKILL.md must start with YAML frontmatter between --- lines"], warnings
    try:
        meta = parse_frontmatter(match.group(1))
    except FrontmatterError as error:
        return [f"frontmatter: {error}"], warnings
    body = match.group(2)

    extra = sorted(set(meta) - ALLOWED)
    if extra:
        errors.append(
            f"unexpected frontmatter fields: {', '.join(extra)}. "
            "Move product-specific settings under metadata as strings, or drop them."
        )

    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required")
    elif len(name) > 64 or not NAME.match(name):
        errors.append(f'name "{name}" must be 1-64 lowercase letters, digits, and single hyphens, not starting or ending with one')
    elif name != folder:
        errors.append(f'name "{name}" must match its folder "{folder}"')

    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description is required")
    elif len(description) > 1024:
        errors.append(f"description is {len(description)} characters (max 1024)")
    else:
        if len(description) < 80:
            warnings.append("description is very short; say what the skill does and when to use it")
        if not TRIGGER.search(description):
            warnings.append('description has no trigger wording ("Use when...", "Triggers on...")')

    for field in ("license", "allowed-tools"):
        if field in meta and (not isinstance(meta[field], str) or not meta[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    if "compatibility" in meta:
        value = meta["compatibility"]
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            errors.append("compatibility must be 1-500 characters")
    if "metadata" in meta:
        value = meta["metadata"]
        if not isinstance(value, dict):
            errors.append("metadata must be a map of string keys to string values")
        else:
            for key, item in value.items():
                if isinstance(item, tuple):
                    errors.append(f'metadata.{key} is {item[1]}, not a string; quote it ("{item[1]}")')

    line_count = source.count("\n") + 1
    if line_count > MAX_LINES:
        errors.append(f"SKILL.md is {line_count} lines; keep it under {MAX_LINES} and move detail into references/")

    prose = re.sub(r"^(```|~~~).*?^\1", "", body, flags=re.S | re.M)
    targets = {
        t for t in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", prose) if not re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I)
    }
    targets |= set(re.findall(r"(?<![\w/.-])((?:scripts|references|assets)/[\w./-]*[\w])", prose))
    for target in sorted(targets):
        if not os.path.exists(os.path.join(skill_dir, target)):
            errors.append(f"SKILL.md references {target}, which doesn't exist")

    references = os.path.join(skill_dir, "references")
    if os.path.isdir(references):
        for entry in sorted(os.listdir(references)):
            path = os.path.join(references, entry)
            if entry.endswith(".md") and os.path.isfile(path):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                if text.count("\n") > 300 and not re.search(r"(?im)^#+\s*(contents|table of contents)\b", text):
                    warnings.append(f"references/{entry} is over 300 lines with no table of contents")

    scripts = os.path.join(skill_dir, "scripts")
    if os.path.isdir(scripts):
        for entry in sorted(os.listdir(scripts)):
            path = os.path.join(scripts, entry)
            if os.path.isfile(path) and not entry.startswith(".") and not os.access(path, os.X_OK):
                warnings.append(f"scripts/{entry} isn't executable (chmod +x)")

    return errors, warnings


def main(argv):
    if not argv or any(arg in ("-h", "--help") for arg in argv):
        print(__doc__.strip())
        return 0 if argv else 2
    failed = 0
    for skill_dir in argv:
        errors, warnings = check(skill_dir)
        label = os.path.basename(os.path.normpath(skill_dir))
        for error in errors:
            print(f"{label}: error: {error}")
        for warning in warnings:
            print(f"{label}: warning: {warning}")
        if errors:
            failed += 1
        elif not warnings:
            print(f"{label}: ok")
    if len(argv) > 1:
        print(f"{len(argv) - failed}/{len(argv)} skills valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
