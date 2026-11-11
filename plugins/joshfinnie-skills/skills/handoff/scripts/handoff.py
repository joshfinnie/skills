#!/usr/bin/env python3
"""Save a handoff document to the temp directory and copy it to the clipboard.

Usage:
    python3 handoff.py --name SLUG < handoff.md
    python3 handoff.py --name SLUG handoff.md
    python3 handoff.py --no-clipboard --name SLUG handoff.md
    python3 handoff.py --dir ~/handoffs --name SLUG handoff.md

Writes <tmp>/handoff-SLUG-YYYYMMDD-HHMMSS.md and refreshes <tmp>/handoff-latest.md,
where <tmp> is /tmp on macOS and Linux. Then copies the document to the system
clipboard with the first tool that works:

  macOS     pbcopy
  WSL       clip.exe (sent as UTF-16LE so non-ASCII text survives)
  Wayland   wl-copy
  X11       xclip, then xsel
  Termux    termux-clipboard-set

Prints the saved path and whether the clipboard copy worked. Exits 1 only if
the file can't be written; a missing clipboard tool is reported, not fatal.
Standard library only.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


def temp_dir():
    return "/tmp" if os.path.isdir("/tmp") and os.access("/tmp", os.W_OK) else tempfile.gettempdir()


def is_wsl():
    try:
        with open("/proc/version", encoding="utf-8") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def clipboard_commands():
    if sys.platform == "darwin":
        yield "pbcopy", ["pbcopy"], "utf-8"
    if sys.platform.startswith("win"):
        yield "clip", ["clip"], "utf-16"
    if is_wsl() and shutil.which("clip.exe"):
        yield "clip.exe", ["clip.exe"], "utf-16"
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        yield "wl-copy", ["wl-copy"], "utf-8"
    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            yield "xclip", ["xclip", "-selection", "clipboard"], "utf-8"
        if shutil.which("xsel"):
            yield "xsel", ["xsel", "--clipboard", "--input"], "utf-8"
    if shutil.which("termux-clipboard-set"):
        yield "termux-clipboard-set", ["termux-clipboard-set"], "utf-8"


def copy(text):
    tried = []
    for name, command, encoding in clipboard_commands():
        data = text.encode("utf-16-le") if encoding == "utf-16" else text.encode("utf-8")
        try:
            subprocess.run(command, input=data, check=True, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return name, tried
        except (OSError, subprocess.SubprocessError):
            tried.append(name)
    return None, tried


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "session"


def main(argv):
    parser = argparse.ArgumentParser(description="Save a handoff document and copy it to the clipboard.")
    parser.add_argument("file", nargs="?", help="Markdown file to hand off (default: stdin)")
    parser.add_argument("--name", default="", help="short label for the filename, e.g. api-pagination")
    parser.add_argument("--no-clipboard", action="store_true", help="save the file only")
    parser.add_argument("--dir", default=None, help="directory to save in (default: /tmp, or the system temp dir)")
    args = parser.parse_args(argv)

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            print(f"Can't read {args.file}: {error.strerror}", file=sys.stderr)
            return 1
    elif sys.stdin.isatty():
        print("Pass a Markdown file or pipe the handoff on stdin. See --help.", file=sys.stderr)
        return 2
    else:
        text = sys.stdin.read()
    if not text.strip():
        print("The handoff is empty; nothing saved.", file=sys.stderr)
        return 1
    text = text.rstrip() + "\n"

    directory = args.dir or temp_dir()
    path = os.path.join(directory, f"handoff-{slugify(args.name)}-{time.strftime('%Y%m%d-%H%M%S')}.md")
    latest = os.path.join(directory, "handoff-latest.md")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        shutil.copyfile(path, latest)
    except OSError as error:
        print(f"Can't write {path}: {error.strerror}", file=sys.stderr)
        return 1

    print(f"Saved: {path}")
    print(f"Also at: {latest}")
    if args.no_clipboard:
        print("Clipboard: skipped (--no-clipboard)")
        return 0
    tool, failed = copy(text)
    if tool:
        print(f"Clipboard: copied with {tool} ({len(text)} characters)")
    else:
        detail = f" ({', '.join(failed)} failed)" if failed else ""
        print(f"Clipboard: no working clipboard tool found{detail}. Open the file above and copy it by hand.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
