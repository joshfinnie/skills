#!/usr/bin/env python3
"""Gather the facts a code review needs before anyone reads a line of code.

Usage:
    python3 branch_context.py [--repo DIR] [--base REF] [--whole-repo] [--max-refs N]

Run it inside the repository. It picks a mode:

  Branch mode (on a feature branch): compares HEAD with its merge base on the
  default branch (origin/HEAD, then main, master, trunk, develop), or --base.
  Whole-repo mode (on the default branch, or with --whole-repo): there is no
  diff, so it maps the codebase for a full review instead.

Branch mode prints:

  - branch, base, merge base, commits, and uncommitted changes
  - changed files with line counts, grouped by kind (code, tests, migrations,
    dependencies, config, CI, docs)
  - symbols the branch adds, removes, or changes (functions, methods, classes,
    types, exported constants) in JS/TS, Python, Go, Rust, Ruby, Java, Kotlin
  - for each changed or removed symbol, the files outside the diff that still
    reference it: the blast radius a reviewer has to check by hand
  - files that import the changed files
  - renamed or removed serialized field names (JSON/YAML/DB tags, serde
    renames) and dropped or renamed SQL columns, with the files outside the
    diff that still use the old name
  - environment variables, routes, and SQL tables the diff touches
  - changed source files that no changed test file mentions

Whole-repo mode prints modules with code and test counts, manifests, CI and
deploy config, churn hotspots from the last six months, the largest code files,
TODO/FIXME/HACK markers, modules with no tests, and recent commits.

Standard library and git only. Read-only: it never checks out or modifies anything.
"""

import argparse
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

KINDS = [
    ("migration", r"(^|/)(migrations?|migrate|db/migrate|alembic/versions|drizzle)/|\.sql$|schema\.prisma$"),
    ("test", r"(^|/)(tests?|__tests__|spec|e2e|testdata)/|[._-](test|spec)\.\w+$|_test\.go$|^test_.*\.py$|/test_[^/]*\.py$"),
    ("dependency", r"(^|/)(package\.json|pnpm-lock\.yaml|package-lock\.json|yarn\.lock|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|pyproject\.toml|poetry\.lock|uv\.lock|requirements[^/]*\.txt|Gemfile(\.lock)?|composer\.(json|lock))$"),
    ("ci", r"(^|/)(\.github/workflows|\.gitlab-ci|\.circleci|Jenkinsfile|\.buildkite)"),
    ("config", r"(^|/)(Dockerfile|docker-compose[^/]*|compose\.ya?ml|fly\.toml|vercel\.json|netlify\.toml|wrangler\.toml|.*\.tf|tsconfig[^/]*\.json|vite\.config\.\w+|next\.config\.\w+|astro\.config\.\w+|\.env[^/]*|[^/]*\.ya?ml|[^/]*\.toml|[^/]*\.ini)$"),
    ("docs", r"\.(md|mdx|rst|txt|adoc)$|(^|/)docs/"),
    ("code", r"\.(jsx?|tsx?|mjs|cjs|mts|cts|vue|svelte|astro|py|go|rs|rb|java|kt|kts|swift|cs|php|ex|exs|scala|c|cc|cpp|h|hpp|m|sh|lua)$"),
]
SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*[(:]"),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"),
    re.compile(r"^\s*type\s+([A-Z]\w*)\s+(?:struct|interface|func|\w)"),
    re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|type)\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!]?)"),
    re.compile(r"^\s*(?:public|protected|private|internal)?\s*(?:static\s+)?(?:final\s+)?(?:suspend\s+)?(?:fun|class|interface|object)\s+([A-Za-z_]\w*)"),
    re.compile(r"^\s*(?:public|protected|private)\s+(?:static\s+)?[\w<>\[\],\s]+\s+([A-Za-z_]\w*)\s*\("),
]
COMMON = {"main", "init", "new", "get", "set", "run", "test", "setup", "handler", "index", "default", "render", "constructor", "String", "Error", "toString", "__init__", "up", "down", "App", "Props"}
ENV = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[['\"]([A-Z][A-Z0-9_]+)|import\.meta\.env\.([A-Z][A-Z0-9_]+)|os\.(?:Getenv|LookupEnv)\(\"([A-Z][A-Z0-9_]+)|os\.environ(?:\.get)?[\[(]['\"]([A-Z][A-Z0-9_]+)|os\.getenv\(['\"]([A-Z][A-Z0-9_]+)|env::var\(\"([A-Z][A-Z0-9_]+)|ENV\[['\"]([A-Z][A-Z0-9_]+)")
ROUTE = re.compile(r"""\b(?:app|router|r|mux|api|server|e|g|group|route|routes)\.(get|post|put|patch|delete|options|head|all|Get|Post|Put|Patch|Delete|HandleFunc|Handle|route|Route)\(\s*[`'"]([^`'"]+)[`'"]|@(?:app|router|bp|api)\.(?:route|get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]|@(Get|Post|Put|Patch|Delete)Mapping\(\s*"?([^")]*)""")
SERIAL_KEY = re.compile(
    r'(?:json|yaml|db|bson|form|xml|mapstructure|toml):"([A-Za-z_][\w-]*)'
    r'|#\[serde\(rename\s*=\s*"([^"]+)"'
    r"|Field\(\s*alias\s*=\s*['\"]([^'\"]+)"
    r'|@JsonProperty\(\s*"([^"]+)"'
    r'|@SerializedName\(\s*"([^"]+)"'
)
DROPPED_COLUMN = re.compile(r"\bdrop\s+column\s+(?:if\s+exists\s+)?[`\"]?(\w+)|\brename\s+column\s+[`\"]?(\w+)", re.I)
TABLE = re.compile(r"\b(?:create|alter|drop)\s+table\s+(?:if\s+(?:not\s+)?exists\s+)?[`\"]?([\w.]+)|\bfrom\s+([a-z_][\w.]*)\s|\binsert\s+into\s+([\w.]+)|\bupdate\s+([a-z_][\w.]*)\s+set\b", re.I)


def git(*args, repo, check=True):
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, errors="replace")
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def default_base(repo):
    head = git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", repo=repo, check=False).strip()
    candidates = [head] if head else []
    candidates += ["origin/main", "origin/master", "main", "master", "trunk", "develop"]
    current = git("rev-parse", "--abbrev-ref", "HEAD", repo=repo).strip()
    for ref in candidates:
        if ref and ref != current and git("rev-parse", "--verify", "-q", ref, repo=repo, check=False).strip():
            return ref
    return None


def kind_of(path):
    for kind, pattern in KINDS:
        if re.search(pattern, path):
            return kind
    return "other"


def symbols_in_diff(diff):
    changed = defaultdict(lambda: {"added": set(), "removed": set(), "touched": set()})
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            continue
        if line.startswith("--- ") or current is None:
            if line.startswith("--- a/"):
                current_old = line[6:]
                changed[current_old]
            continue
        if line.startswith("@@"):
            context = line.split("@@")[-1]
            for pattern in SYMBOL_PATTERNS:
                match = pattern.match(context.strip())
                if match:
                    changed[current]["touched"].add(match.group(1))
                    break
            continue
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            for pattern in SYMBOL_PATTERNS:
                match = pattern.match(line[1:])
                if match:
                    changed[current]["added" if line[0] == "+" else "removed"].add(match.group(1))
                    break
    return changed


def references(symbol, repo, exclude):
    out = git("grep", "-l", "-w", "-I", "-e", symbol, "--", ".", repo=repo, check=False)
    return [f for f in out.splitlines() if f not in exclude]


def importers(path, repo, exclude):
    stem = os.path.splitext(path)[0]
    parts = stem.split("/")
    needles = set()
    base = parts[-1]
    if base in ("index", "__init__", "mod") and len(parts) > 1:
        base = parts[-2]
        needles.add("/".join(parts[-3:-1]) if len(parts) > 2 else parts[-2])
    else:
        needles.add("/".join(parts[-2:]) if len(parts) > 1 else base)
    if path.endswith(".py"):
        needles.add(".".join(parts[-2:]) if len(parts) > 1 else base)
    if path.endswith(".go"):
        needles = {"/".join(parts[:-1])} if len(parts) > 1 else set()
    found = set()
    for needle in needles:
        if not needle:
            continue
        out = git("grep", "-l", "-F", "-I", "-e", needle, "--", ".", repo=repo, check=False)
        found.update(f for f in out.splitlines() if f not in exclude and kind_of(f) in ("code", "test"))
    return sorted(found)


CONTAINERS = {"src", "app", "apps", "packages", "internal", "cmd", "lib", "pkg", "services", "server", "client", "web", "crates", "modules"}


def module_of(path):
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    if parts[0] in CONTAINERS and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0]


def line_count(repo, path):
    try:
        with open(os.path.join(repo, path), "rb") as handle:
            return handle.read().count(b"\n")
    except OSError:
        return 0


def whole_repo(repo, branch, max_refs):
    files = [f for f in git("ls-files", repo=repo).splitlines() if f]
    head = git("log", "-1", "--format=%h %s (%cr)", repo=repo).strip()
    print(f"# Whole-repo context: {os.path.basename(repo)} on {branch}\n")
    print(f"HEAD: {head}")
    print(f"Tracked files: {len(files)}")
    authors = git("shortlog", "-sn", "--all", "--no-merges", repo=repo, check=False).strip().splitlines()
    print(f"Contributors: {len(authors)}")

    kinds = defaultdict(list)
    for f in files:
        kinds[kind_of(f)].append(f)
    exts = Counter(os.path.splitext(f)[1] for f in kinds["code"])
    print("Languages: " + ", ".join(f"{e} {n}" for e, n in exts.most_common(8)))

    print("\n## Modules (code files / test files / lines of code)")
    code_by, test_by, loc_by = Counter(), Counter(), Counter()
    for f in kinds["code"]:
        code_by[module_of(f)] += 1
        loc_by[module_of(f)] += line_count(repo, f)
    for f in kinds["test"]:
        test_by[module_of(f)] += 1
    for module in sorted(set(code_by) | set(test_by)):
        print(f"- {module}: {code_by[module]} code, {test_by[module]} tests, {loc_by[module]} lines")
    untested = [m for m in code_by if code_by[m] >= 3 and test_by[m] == 0]
    if untested:
        print("Modules with 3+ code files and no tests: " + ", ".join(sorted(untested)))

    for kind, title in (("dependency", "Dependency manifests and lockfiles"), ("ci", "CI"), ("config", "Deploy and build config"), ("migration", "Migrations and schema")):
        if kinds[kind]:
            listed = kinds[kind][:max_refs * 2]
            more = f" ... and {len(kinds[kind]) - len(listed)} more" if len(kinds[kind]) > len(listed) else ""
            print(f"\n## {title}\n" + "\n".join(f"- {f}" for f in listed) + more)

    churn = Counter(f for f in git("log", "--since=6.months", "--no-merges", "--format=", "--name-only", repo=repo, check=False).splitlines() if f in set(files) and kind_of(f) == "code")
    print("\n## Churn hotspots (code files changed most in the last 6 months, with size)")
    for f, n in churn.most_common(15):
        print(f"- {f}: {n} commits, {line_count(repo, f)} lines")
    if not churn:
        print("(no commits in the last 6 months)")

    print("\n## Largest code files")
    for f in sorted(kinds["code"], key=lambda f: -line_count(repo, f))[:12]:
        print(f"- {f}: {line_count(repo, f)} lines")

    markers = git("grep", "-n", "-I", "-E", r"\b(TODO|FIXME|HACK|XXX)\b", "--", ".", repo=repo, check=False).splitlines()
    markers = [m for m in markers if kind_of(m.split(":", 1)[0]) in ("code", "test", "config")]
    print(f"\n## TODO/FIXME/HACK/XXX markers in code ({len(markers)})")
    for m in markers[:15]:
        path, line, text = (m.split(":", 2) + ["", ""])[:3]
        print(f"- {path}:{line}: {text.strip()[:100]}")
    if len(markers) > 15:
        print(f"... and {len(markers) - 15} more")

    print("\n## Recent commits")
    print(git("log", "-15", "--no-merges", "--format=%h %ad %an: %s", "--date=short", repo=repo).strip())
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Gather context for reviewing a git branch.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", help="base ref to compare against (default: merge base with the default branch)")
    parser.add_argument("--whole-repo", action="store_true", help="review the whole codebase instead of a branch diff")
    parser.add_argument("--max-refs", type=int, default=12, help="max referencing files listed per symbol")
    args = parser.parse_args(argv)
    repo = os.path.abspath(args.repo)

    try:
        git("rev-parse", "--git-dir", repo=repo)
    except RuntimeError:
        print(f"Not a git repository: {repo}", file=sys.stderr)
        return 2

    if not git("rev-parse", "--verify", "-q", "HEAD", repo=repo, check=False).strip():
        print("This repository has no commits yet, so there's nothing to review. Commit something first.", file=sys.stderr)
        return 2
    branch = git("rev-parse", "--abbrev-ref", "HEAD", repo=repo).strip()
    origin_head = git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD", repo=repo, check=False).strip()
    default_names = {origin_head.split("/", 1)[-1]} if origin_head else {"main", "master", "trunk", "develop"}
    if args.whole_repo or (not args.base and branch in default_names):
        return whole_repo(repo, branch, args.max_refs)
    base = args.base or default_base(repo)
    if not base:
        print("Couldn't find a default branch to compare against. Pass --base <ref>.", file=sys.stderr)
        return 2
    try:
        merge_base = git("merge-base", base, "HEAD", repo=repo).strip()
    except RuntimeError as error:
        print(f"Can't find a merge base between {base} and HEAD: {error}", file=sys.stderr)
        return 2
    span = f"{merge_base}..HEAD"

    print(f"# Branch context: {branch}\n")
    print(f"Base: {base} (merge base {merge_base[:10]})")
    behind = git("rev-list", "--count", f"HEAD..{base}", repo=repo, check=False).strip()
    if behind and behind != "0":
        print(f"Note: {base} has {behind} commit(s) not in this branch; the review covers only this branch's changes.")

    print("\n## Commits")
    log = git("log", "--reverse", "--format=%h %an: %s", span, repo=repo).strip()
    print(log or "(no commits on this branch)")

    status = git("status", "--porcelain", repo=repo).strip()
    if status:
        print("\n## Uncommitted changes (not part of the branch diff below)")
        print(status)

    numstat = git("diff", "--numstat", "-M", span, repo=repo).strip()
    if not numstat:
        print("\nNo committed changes between the base and HEAD.")
        return 0
    files = []
    for line in numstat.splitlines():
        added, removed, path = line.split("\t", 2)
        if " => " in path:
            path = re.sub(r"\{([^}]*) => ([^}]*)\}", r"\2", path).split(" => ")[-1]
        files.append((path, added, removed))
    changed_paths = {p for p, _, _ in files}

    print(f"\n## Changed files ({len(files)})")
    by_kind = defaultdict(list)
    for path, added, removed in files:
        by_kind[kind_of(path)].append(f"{path} (+{added} -{removed})")
    for kind in ["code", "test", "migration", "dependency", "config", "ci", "docs", "other"]:
        if by_kind.get(kind):
            print(f"\n{kind}:")
            for entry in by_kind[kind]:
                print(f"  {entry}")

    diff = git("diff", "-M", "-U3", span, repo=repo)

    print("\n## Symbols the branch changes")
    symbols = symbols_in_diff(diff)
    blast = {}
    for path in sorted(p for p in symbols if p):
        info = symbols[path]
        added = info["added"] - info["removed"]
        removed = info["removed"] - info["added"]
        modified = (info["added"] & info["removed"]) | (info["touched"] - added - removed)
        if not (added or removed or modified):
            continue
        print(f"\n{path}")
        if added:
            print(f"  added: {', '.join(sorted(added))}")
        if modified:
            print(f"  changed, or near a change: {', '.join(sorted(modified))}")
        if removed:
            print(f"  removed: {', '.join(sorted(removed))}")
        for name in modified | removed:
            if len(name) > 2 and name not in COMMON:
                blast.setdefault(name, set()).add(path)

    print("\n## Blast radius: files outside the diff that reference changed or removed symbols")
    any_refs = False
    for name in sorted(blast):
        all_refs = references(name, repo, changed_paths)
        refs = [f for f in all_refs if kind_of(f) != "docs"]
        docs = len(all_refs) - len(refs)
        if refs:
            any_refs = True
            more = f" ... and {len(refs) - args.max_refs} more" if len(refs) > args.max_refs else ""
            note = f" (+{docs} docs)" if docs else ""
            print(f"- {name} (from {', '.join(sorted(blast[name]))}): {', '.join(refs[:args.max_refs])}{more}{note}")
    if not any_refs:
        print("(none found by name; still check dynamic dispatch, reflection, string-keyed lookups, and other services)")

    print("\n## Files outside the diff that import changed code files")
    any_importers = False
    for path, _, _ in files:
        if kind_of(path) != "code":
            continue
        users = importers(path, repo, changed_paths)
        if users:
            any_importers = True
            more = f" ... and {len(users) - args.max_refs} more" if len(users) > args.max_refs else ""
            print(f"- {path}: {', '.join(users[:args.max_refs])}{more}")
    if not any_importers:
        print("(none found)")

    added_lines = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed_lines = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

    def collect(pattern, text):
        found = set()
        for match in pattern.finditer(text):
            groups = [g for g in match.groups() if g]
            if groups:
                found.add(groups[-1] if pattern is not ROUTE else " ".join(groups).upper().replace(groups[-1].upper(), groups[-1]))
        return found

    def names(pattern, text):
        return {next(g for g in m.groups() if g) for m in pattern.finditer(text) if any(m.groups())}

    print("\n## Renamed or removed names that other code may still use")
    gone = [("serialized field", n) for n in sorted(names(SERIAL_KEY, removed_lines) - names(SERIAL_KEY, added_lines))]
    gone += [("SQL column", n) for n in sorted(names(DROPPED_COLUMN, added_lines))]
    any_gone = False
    for label, name in gone:
        hits = git("grep", "-n", "-w", "-I", "-e", name, "--", ".", repo=repo, check=False).splitlines()
        hits = [h for h in hits if h.split(":", 1)[0] not in changed_paths and kind_of(h.split(":", 1)[0]) not in ("docs",)]
        any_gone = True
        if hits:
            files_hit = sorted({h.split(":", 1)[0] for h in hits})
            print(f"- {label} \"{name}\": still used in {len(hits)} place(s) outside the diff: {', '.join(files_hit[:args.max_refs])}")
            for hit in hits[:6]:
                path, line, text = (hit.split(":", 2) + ["", ""])[:3]
                print(f"    {path}:{line}: {text.strip()[:110]}")
        else:
            print(f"- {label} \"{name}\": no other uses found by name")
    if not any_gone:
        print("(none)")

    print("\n## Interfaces the diff touches")
    for label, pattern in (("Environment variables", ENV), ("Routes", ROUTE), ("SQL tables", TABLE)):
        plus, minus = collect(pattern, added_lines), collect(pattern, removed_lines)
        if plus or minus:
            print(f"{label}:")
            for item in sorted(plus - minus):
                print(f"  + {item}")
            for item in sorted(minus - plus):
                print(f"  - {item}")
            for item in sorted(plus & minus):
                print(f"  ~ {item}")

    tests = [p for p, _, _ in files if kind_of(p) == "test"]
    test_text = "\n".join(git("show", f"HEAD:{t}", repo=repo, check=False) for t in tests)
    untested = []
    for path, _, _ in files:
        if kind_of(path) == "code":
            stem = os.path.splitext(os.path.basename(path))[0]
            if stem not in ("index", "__init__", "mod", "main") and not re.search(r"\b" + re.escape(stem) + r"\b", test_text):
                untested.append(path)
    print("\n## Changed code files that no changed test mentions")
    print("\n".join(f"- {p}" for p in untested) or "(every changed code file is mentioned by a changed test)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
