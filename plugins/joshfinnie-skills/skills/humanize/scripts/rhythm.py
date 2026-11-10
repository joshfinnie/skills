#!/usr/bin/env python3
"""Measure sentence-length rhythm in prose and flag flat stretches.

Usage:
    python3 rhythm.py FILE [FILE ...]
    cat draft.md | python3 rhythm.py

Prints each paragraph's sentence lengths in words and flags:
  - flat runs: 3+ consecutive sentences within a few words of each other
  - paragraphs of 4+ sentences with no short (<= 8 words) sentence
  - paragraphs of 4+ sentences with no long (>= 20 words) sentence
For sections with several paragraphs it repeats the checks across the whole
section (headings start a new one), since splitting prose into short
paragraphs can hide a flat stretch.

Markdown frontmatter, fenced code, headings, tables, list items, and HTML
are skipped, since rhythm only applies to running prose. Standard library only.
"""

import re
import sys

SHORT = 8
LONG = 20
RUN_MIN = 3
RUN_SPREAD = 4

ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
    "st", "no", "fig", "approx", "inc", "ltd", "co", "u.s", "a.m", "p.m",
}

SENTENCE_END = re.compile(r"""([.!?]+)(["')\]*_]*)\s+(?=["'(\[*_`]*[A-Z0-9])""")
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-/]*")
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")


def paragraphs(text):
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break

    blocks, current, fence = [], [], None
    for line in lines:
        stripped = line.strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            if marker and stripped.startswith(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        skip = (
            not stripped
            or stripped.startswith(("#", "|", "<"))
            or LIST_ITEM.match(line)
            or re.fullmatch(r"[-*_]{3,}", stripped)
        )
        if skip:
            if current:
                blocks.append(" ".join(current))
                current = []
            if stripped.startswith("#"):
                blocks.append(None)
            continue
        if stripped.endswith(":") and len(stripped.split()) <= 5 and not current:
            continue
        current.append(re.sub(r"^>\s?", "", stripped))
    if current:
        blocks.append(" ".join(current))
    return blocks


def sentences(paragraph):
    parts, start = [], 0
    for match in SENTENCE_END.finditer(paragraph):
        before = paragraph[start:match.start()].split()
        last = before[-1].lower().rstrip(".") if before else ""
        if match.group(1) == "." and (last in ABBREVIATIONS or re.fullmatch(r"[a-z]", last)):
            continue
        parts.append(paragraph[start:match.end()].strip())
        start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if WORD.search(p)]


def word_count(sentence):
    return len(WORD.findall(sentence))


def flat_runs(lengths):
    runs, i = [], 0
    while i < len(lengths):
        j = i
        while j + 1 < len(lengths) and max(lengths[i:j + 2]) - min(lengths[i:j + 2]) <= RUN_SPREAD:
            j += 1
        if j - i + 1 >= RUN_MIN:
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def clip(sentence, width=60):
    return sentence if len(sentence) <= width else sentence[: width - 3].rstrip() + "..."


def section_checks(every, owner):
    lengths = [n for _, n in every]
    notes = []
    for a, b in flat_runs(lengths):
        if owner[a] != owner[b]:
            notes.append(
                f"flat run across paragraphs ¶{owner[a]}-¶{owner[b]} ({min(lengths[a:b + 1])}-{max(lengths[a:b + 1])} words): "
                f'"{clip(every[a][0])}" ... "{clip(every[b][0])}"'
            )
    if len(lengths) >= 6 and min(lengths) > SHORT:
        notes.append(f"no short sentence (<= {SHORT} words) in this section")
    if len(lengths) >= 6 and max(lengths) < LONG:
        notes.append(f"no long sentence (>= {LONG} words) in this section")
    groups = " | ".join(" ".join(str(n) for (_, n), o in zip(every, owner) if o == p) for p in dict.fromkeys(owner))
    print(f"Section ¶{owner[0]}-¶{owner[-1]}: {groups}")
    for note in notes:
        print(f"  ! {note}")
    return bool(notes)


def report(text, label=None):
    flagged = 0
    total = 0
    every, owner = [], []
    if label:
        print(f"== {label}")
    number = 0
    for paragraph in paragraphs(text) + [None]:
        if paragraph is None:
            if len(set(owner)) > 1:
                flagged += section_checks(every, owner)
            every, owner = [], []
            continue
        number += 1
        sents = sentences(paragraph)
        if not sents:
            continue
        lengths = [word_count(s) for s in sents]
        every.extend(zip(sents, lengths))
        owner.extend([number] * len(sents))
        total += len(sents)
        print(f"¶{number} ({len(sents)} sentence{'s' if len(sents) != 1 else ''}): {' '.join(map(str, lengths))}")
        notes = []
        for a, b in flat_runs(lengths):
            notes.append(
                f"flat run, sentences {a + 1}-{b + 1} ({min(lengths[a:b + 1])}-{max(lengths[a:b + 1])} words): "
                f'"{clip(sents[a])}" ... "{clip(sents[b])}"'
            )
        if len(sents) >= 4 and min(lengths) > SHORT:
            notes.append(f"no short sentence (<= {SHORT} words)")
        if len(sents) >= 4 and max(lengths) < LONG:
            notes.append(f"no long sentence (>= {LONG} words)")
        for note in notes:
            print(f"  ! {note}")
        flagged += bool(notes)
    if total == 0:
        print("No prose found.")
    else:
        print(f"{flagged} flag group{'s' if flagged != 1 else ''}, {total} sentences checked.")
    return flagged


def main(argv):
    if any(arg in ("-h", "--help") for arg in argv):
        print(__doc__.strip())
        return 0
    if not argv:
        if sys.stdin.isatty():
            print("Pass a file path or pipe text on stdin. See --help.", file=sys.stderr)
            return 2
        report(sys.stdin.read())
        return 0
    for index, path in enumerate(argv):
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            print(f"Can't read {path}: {error.strerror}", file=sys.stderr)
            return 2
        if index:
            print()
        report(text, path if len(argv) > 1 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
