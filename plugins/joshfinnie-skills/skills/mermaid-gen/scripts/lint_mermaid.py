#!/usr/bin/env python3
"""Catch common Mermaid mistakes that stop a diagram from rendering.

Usage:
    python3 lint_mermaid.py FILE [FILE ...]

FILE can be Markdown (every ```mermaid block is checked) or a raw .mmd file.
Checks flowcharts and ER diagrams for the errors that most often break
rendering on GitHub: unquoted special characters in node labels, reserved
words used as node ids, unbalanced subgraph/end, malformed ER relationships
and attributes, and diagrams too large to read. Exits 1 if any errors are found.

This is a fast pre-check, not a full parser. When @mermaid-js/mermaid-cli is
installed, `mmdc -i FILE -o /tmp/out.svg` is the final word.
"""

import re
import sys

RESERVED_IDS = {"end", "graph", "subgraph", "flowchart", "style", "classdef", "class", "click", "linkstyle", "direction", "default"}
SHAPES = [("([", "])"), ("[[", "]]"), ("[(", ")]"), ("((", "))"), ("{{", "}}"), ("[/", "/]"), ("[\\", "\\]"), ("[/", "\\]"), ("[\\", "/]"), ("[", "]"), ("(", ")"), ("{", "}"), (">", "]")]
LABEL_SPECIAL = re.compile(r"[()\[\]{}<>\"|;#]")
NODE = re.compile(r"(?<![\w-])([A-Za-z_][\w-]*)\s*(\(\[|\[\[|\[\(|\(\(|\{\{|\[/|\[\\|\[|\(|\{|>)")
ER_REL = re.compile(r"^\s*([\w-]+)\s+(\|o|\|\||\}o|\}\|)(--|\.\.)(o\||\|\||o\{|\|\{)\s+([\w-]+)\s*:\s*(.+)$")
ER_ATTR = re.compile(r'^\s*([A-Za-z][\w\-()\[\],]*)\s+([A-Za-z_*][\w-]*)(\s+(PK|FK|UK)(\s*,\s*(PK|FK|UK))*)?(\s+"[^"]*")?\s*$')
MAX_NODES = 30


def blocks(path, text):
    if path.endswith((".mmd", ".mermaid")):
        return [(1, text)]
    found = []
    for match in re.finditer(r"^(```|~~~)\s*mermaid\s*\n(.*?)^\1\s*$", text, re.S | re.M):
        found.append((text[: match.start()].count("\n") + 2, match.group(2)))
    return found


def closing_for(line, start, opener):
    for o, c in SHAPES:
        if o == opener:
            depth_open = line.find(c, start)
            return depth_open, c
    return -1, None


def lint_flowchart(lines, first):
    errors, warnings = [], []
    nodes, depth = set(), 0
    for offset, raw in enumerate(lines[1:], 1):
        line = re.sub(r"%%.*$", "", raw).strip()
        where = first + offset
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith("subgraph"):
            depth += 1
            continue
        if lowered == "end":
            depth -= 1
            if depth < 0:
                errors.append(f"line {where}: 'end' with no open subgraph")
                depth = 0
            continue
        if lowered.startswith(("classdef", "class ", "style ", "linkstyle", "click ", "direction ")):
            continue
        for match in NODE.finditer(line):
            node_id, opener = match.group(1), match.group(2)
            start = match.end()
            if line[start:start + 1] == '"':
                close_quote = line.find('"', start + 1)
                if close_quote == -1:
                    errors.append(f'line {where}: unclosed quote in label of "{node_id}"')
                nodes.add(node_id)
                continue
            close_at, closer = closing_for(line, start, opener)
            if close_at == -1:
                continue
            label = line[start:close_at]
            nodes.add(node_id)
            if node_id.lower() in RESERVED_IDS:
                errors.append(f'line {where}: node id "{node_id}" is a reserved word; rename it (e.g. "{node_id}Node")')
            if LABEL_SPECIAL.search(label):
                errors.append(f'line {where}: label "{label}" on "{node_id}" has special characters; quote it: {node_id}{opener}"{label}"{closer}')
        for edge_label in re.findall(r"\|([^|]*)\|", line):
            if '"' not in edge_label and re.search(r"[()\[\]{}]", edge_label):
                errors.append(f'line {where}: edge label |{edge_label}| has brackets; quote it: |"{edge_label}"|')
        bare = re.findall(r"(?:^|-->|---|-\.->|==>|--[^>-]*-->)\s*([A-Za-z_][\w-]*)\s*(?=$|-->|---|-\.->|==>|;|&)", line)
        for node_id in bare:
            if node_id.lower() in RESERVED_IDS:
                errors.append(f'line {where}: node id "{node_id}" is a reserved word; rename it')
            nodes.add(node_id)
    if depth > 0:
        errors.append(f"{depth} subgraph(s) never closed with 'end'")
    if len(nodes) > MAX_NODES:
        warnings.append(f"{len(nodes)} nodes; over {MAX_NODES} gets hard to read, so group into subgraphs or split the diagram")
    return errors, warnings


def lint_er(lines, first):
    errors, warnings = [], []
    entities, in_entity = set(), None
    for offset, raw in enumerate(lines[1:], 1):
        line = re.sub(r"%%.*$", "", raw).strip()
        where = first + offset
        if not line:
            continue
        if in_entity:
            if line == "}":
                in_entity = None
            elif not ER_ATTR.match(line):
                errors.append(f'line {where}: attribute "{line}" in {in_entity} should be: type name [PK|FK|UK] ["comment"], with no spaces in the type')
            continue
        entity = re.match(r'^([\w-]+)(\s*\["[^"]*"\])?\s*\{\s*$', line)
        if entity:
            in_entity = entity.group(1)
            entities.add(in_entity)
            continue
        if re.match(r"^[\w-]+\s*\{\s*\}$", line):
            entities.add(line.split("{")[0].strip())
            continue
        rel = ER_REL.match(line)
        if rel:
            entities.update({rel.group(1), rel.group(5)})
            label = rel.group(6).strip()
            if " " in label and not (label.startswith('"') and label.endswith('"')):
                errors.append(f'line {where}: relationship label {label} has spaces; quote it: "{label}"')
            continue
        if "--" in line or ".." in line:
            errors.append(f'line {where}: relationship "{line}" should look like: A ||--o{{ B : "label" (cardinalities |o || }}o }}| / o| || o{{ |{{)')
        else:
            errors.append(f'line {where}: unrecognized line "{line}"')
    if in_entity:
        errors.append(f"entity {in_entity} is missing its closing }}")
    if len(entities) > MAX_NODES:
        warnings.append(f"{len(entities)} entities; consider splitting by domain")
    return errors, warnings


def lint_block(source, first):
    lines = source.splitlines()
    while lines and (not lines[0].strip() or lines[0].strip().startswith("%%")):
        lines.pop(0)
        first += 1
    if not lines:
        return ["empty mermaid block"], []
    kind = lines[0].split()[0]
    if kind in ("flowchart", "graph"):
        if len(lines[0].split()) > 1 and lines[0].split()[1] not in ("TB", "TD", "BT", "RL", "LR"):
            return [f"line {first}: unknown direction {lines[0].split()[1]}; use TB, TD, BT, RL, or LR"], []
        return lint_flowchart(lines, first)
    if kind == "erDiagram":
        return lint_er(lines, first)
    known = {"sequenceDiagram", "classDiagram", "stateDiagram", "stateDiagram-v2", "gantt", "pie", "journey", "gitGraph", "mindmap", "timeline", "C4Context", "C4Container", "C4Component", "block-beta", "architecture-beta", "quadrantChart", "requirementDiagram", "sankey-beta", "xychart-beta"}
    if kind not in known:
        return [f"line {first}: unknown diagram type {kind!r}"], []
    return [], [f"line {first}: {kind} isn't checked by this linter"]


def main(argv):
    if not argv or any(a in ("-h", "--help") for a in argv):
        print(__doc__.strip())
        return 0 if argv else 2
    failed = False
    for path in argv:
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            print(f"{path}: can't read: {error.strerror}", file=sys.stderr)
            return 2
        found = blocks(path, text)
        if not found:
            print(f"{path}: no mermaid blocks found")
            failed = True
            continue
        for first, source in found:
            errors, warnings = lint_block(source, first)
            for message in errors:
                print(f"{path}: error: {message}")
            for message in warnings:
                print(f"{path}: warning: {message}")
            failed = failed or bool(errors)
        if not failed:
            print(f"{path}: {len(found)} diagram(s) ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
