#!/usr/bin/env python3
"""Survey a codebase for diagramming: layout, entry points, data model
sources, external services, and the internal import graph between modules.

Usage:
    python3 survey.py [REPO_DIR] [--depth N] [--max-edges N]

REPO_DIR defaults to the current directory. Files come from `git ls-files`
when REPO_DIR is a git repository, so ignored and vendored files are skipped.

The import graph covers JavaScript/TypeScript, Python, Go, and Rust. Edges are
grouped by module: a top-level directory, or two levels deep under container
directories like src/, apps/, packages/, internal/, cmd/ (change with --depth).
Only imports that resolve to a file inside the repo count, so every edge printed
is backed by real import statements. Standard library only.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", ".next", ".nuxt",
    ".svelte-kit", ".astro", "__pycache__", ".venv", "venv", ".tox", "coverage", ".turbo",
}
CONTAINERS = {"src", "app", "apps", "packages", "internal", "cmd", "lib", "pkg", "services", "server", "client", "web", "crates", "modules"}
CODE_EXT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte", ".astro", ".py", ".go", ".rs"}
JS_EXT = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro"]
MANIFESTS = {
    "package.json", "pnpm-workspace.yaml", "go.mod", "Cargo.toml", "pyproject.toml", "requirements.txt",
    "setup.py", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "composer.json", "mix.exs",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "fly.toml",
    "vercel.json", "netlify.toml", "wrangler.toml", "serverless.yml", "Procfile", "turbo.json", "nx.json",
}
SCHEMA_PATTERNS = [
    (r"(^|/)schema\.prisma$", "Prisma schema"),
    (r"(^|/)migrations?/.*\.sql$", "SQL migration"),
    (r"(^|/)(schema|structure)\.sql$", "SQL schema"),
    (r"(^|/)db/schema\.rb$", "Rails schema"),
    (r"(^|/)models?\.py$|(^|/)models/[^/]+\.py$", "Python models"),
    (r"(^|/)drizzle/.*schema.*\.[jt]s$|(^|/)schema/[^/]+\.[jt]s$|(^|/)db/schema\.[jt]s$", "TS schema"),
    (r"\.entity\.[jt]s$", "TypeORM entity"),
    (r"\.model\.[jt]s$", "Model module"),
    (r"(^|/)ent/schema/[^/]+\.go$", "Ent schema"),
    (r"(^|/)models?/[^/]+\.go$", "Go models"),
    (r"\.graphql$|\.gql$", "GraphQL schema"),
    (r"\.proto$", "Protobuf"),
    (r"(^|/)supabase/.*\.sql$", "Supabase SQL"),
]
SERVICE_HINTS = {
    "PostgreSQL": r"^(pg|postgres|pg-promise|@neondatabase/serverless|psycopg2?|asyncpg|github\.com/(jackc/pgx|lib/pq))",
    "MySQL": r"^(mysql2?|pymysql|github\.com/go-sql-driver/mysql)",
    "SQLite": r"^(better-sqlite3|sqlite3?|@libsql/client|modernc\.org/sqlite|github\.com/mattn/go-sqlite3|rusqlite)",
    "MongoDB": r"^(mongodb|mongoose|pymongo|motor)",
    "Redis": r"^(redis|ioredis|@upstash/redis|github\.com/(redis|go-redis)/)",
    "Prisma": r"^(@prisma/client|prisma)$",
    "Drizzle": r"^drizzle-orm",
    "Supabase": r"^@supabase/",
    "SQLAlchemy": r"^sqlalchemy",
    "Stripe": r"^(stripe|@stripe/|github\.com/stripe/)",
    "AWS": r"^(@aws-sdk/|aws-sdk|boto3|github\.com/aws/)",
    "Google Cloud": r"^(@google-cloud/|google-cloud-)",
    "Kafka": r"^(kafkajs|confluent-kafka|github\.com/segmentio/kafka-go)",
    "RabbitMQ": r"^(amqplib|pika|github\.com/rabbitmq/)",
    "OpenAI": r"^openai$",
    "Anthropic": r"^(@anthropic-ai/|anthropic$)",
    "Bluesky/AT Protocol": r"^(@atproto/|github\.com/bluesky-social/)",
    "Resend/email": r"^(resend|nodemailer|@sendgrid/|postmark)",
    "Auth": r"^(next-auth|@auth/|@clerk/|lucia|better-auth|passport)",
    "Sentry": r"^@sentry/",
}

JS_IMPORT = re.compile(r"""(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\s*\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\)|^\s*import\s+['"]([^'"]+)['"]""", re.M)
PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import|import\s+([\w.]+))", re.M)
GO_IMPORT_BLOCK = re.compile(r"import\s*\((.*?)\)", re.S)
GO_IMPORT_LINE = re.compile(r'import\s+(?:\w+\s+)?"([^"]+)"')
RUST_USE = re.compile(r"^\s*(?:pub\s+)?use\s+crate::(\w+)|^\s*(?:pub\s+)?mod\s+(\w+)\s*;", re.M)


def list_files(root):
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=True).stdout
        files = [f for f in out.splitlines() if f and os.path.isfile(os.path.join(root, f))]
        if files:
            return sorted(files)
    except (OSError, subprocess.CalledProcessError):
        pass
    files = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in names:
            files.append(os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/"))
    return sorted(files)


def read(root, path, limit=400_000):
    try:
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def module_of(path, depth):
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    if depth:
        return "/".join(parts[: min(depth, len(parts) - 1)])
    if parts[0] in CONTAINERS and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0]


def js_aliases(root, files):
    aliases = {}
    for config in [f for f in files if re.search(r"(^|/)(tsconfig|jsconfig)[^/]*\.json$", f)]:
        text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", read(root, config), flags=re.S)
        text = re.sub(r",(\s*[}\]])", r"\1", text)
        try:
            options = json.loads(text).get("compilerOptions", {})
        except (ValueError, AttributeError):
            continue
        base = os.path.normpath(os.path.join(os.path.dirname(config), options.get("baseUrl", "."))).replace(os.sep, "/")
        for alias, targets in (options.get("paths") or {}).items():
            if targets:
                prefix = alias.rstrip("*")
                target = os.path.normpath(os.path.join(base, targets[0].rstrip("*"))).replace(os.sep, "/")
                aliases[prefix] = target.lstrip("./") + ("/" if prefix.endswith("/") else "")
    return aliases


def workspace_packages(root, files):
    packages = {}
    for manifest in [f for f in files if os.path.basename(f) == "package.json" and "/" in f]:
        try:
            name = json.loads(read(root, manifest)).get("name")
        except (ValueError, AttributeError):
            continue
        if name:
            packages[name] = os.path.dirname(manifest)
    return packages


def resolve_js(spec, source, fileset, aliases, packages=None):
    for name, directory in (packages or {}).items():
        if spec == name or spec.startswith(name + "/"):
            inside = spec[len(name):].lstrip("/")
            prefix = f"{directory}/{inside}" if inside else directory
            hit = next((f for f in fileset if f.startswith(prefix + "/") or f.startswith(prefix + ".")), None)
            if hit:
                return hit
    if spec.startswith("."):
        target = os.path.normpath(os.path.join(os.path.dirname(source), spec)).replace(os.sep, "/")
    else:
        target = None
        for prefix, replacement in sorted(aliases.items(), key=lambda item: -len(item[0])):
            if prefix and spec.startswith(prefix):
                target = replacement + spec[len(prefix):]
                break
        if target is None:
            return None
    target = target.lstrip("./") if target.startswith("./") else target
    candidates = [target] + [target + ext for ext in JS_EXT] + [f"{target}/index{ext}" for ext in JS_EXT]
    stripped = re.sub(r"\.(js|jsx|mjs|cjs)$", "", target)
    candidates += [stripped + ext for ext in JS_EXT]
    return next((c for c in candidates if c in fileset), None)


def resolve_py(spec, source, fileset):
    if spec.startswith("."):
        dots = len(spec) - len(spec.lstrip("."))
        base = os.path.dirname(source)
        for _ in range(dots - 1):
            base = os.path.dirname(base)
        rest = spec.lstrip(".").replace(".", "/")
        target = f"{base}/{rest}" if rest else base
    else:
        target = spec.replace(".", "/")
    for prefix in ["", "src/"]:
        for candidate in (f"{prefix}{target}.py", f"{prefix}{target}/__init__.py"):
            if candidate.lstrip("/") in fileset:
                return candidate.lstrip("/")
        parent = os.path.dirname(f"{prefix}{target}")
        if parent and f"{parent}.py" in fileset:
            return f"{parent}.py"
    return None


def go_module_paths(root, files):
    modules = {}
    for gomod in [f for f in files if f.endswith("go.mod")]:
        match = re.search(r"^module\s+(\S+)", read(root, gomod), re.M)
        if match:
            modules[match.group(1)] = os.path.dirname(gomod)
    return modules


def import_edges(root, files, depth):
    fileset = set(files)
    aliases = js_aliases(root, files)
    packages = workspace_packages(root, files)
    go_modules = go_module_paths(root, files)
    go_dirs = defaultdict(list)
    for f in files:
        if f.endswith(".go"):
            go_dirs[os.path.dirname(f)].append(f)
    edges = Counter()
    for source in files:
        ext = os.path.splitext(source)[1]
        if ext not in CODE_EXT or re.search(r"(^|/)(test|tests|__tests__|e2e|fixtures?)/|\.(test|spec)\.", source):
            continue
        text = read(root, source)
        targets = []
        if ext in JS_EXT:
            for groups in JS_IMPORT.findall(text):
                spec = next(g for g in groups if g)
                targets.append(resolve_js(spec, source, fileset, aliases, packages))
        elif ext == ".py":
            for frm, imp in PY_IMPORT.findall(text):
                targets.append(resolve_py(frm or imp, source, fileset))
        elif ext == ".go":
            specs = GO_IMPORT_LINE.findall(text)
            for block in GO_IMPORT_BLOCK.findall(text):
                specs += re.findall(r'"([^"]+)"', block)
            for spec in specs:
                for module_path, module_dir in go_modules.items():
                    if spec == module_path or spec.startswith(module_path + "/"):
                        directory = os.path.join(module_dir, spec[len(module_path):].lstrip("/")).strip("/")
                        if go_dirs.get(directory):
                            targets.append(go_dirs[directory][0])
        elif ext == ".rs":
            crate_root = source.split("src/")[0] + "src/" if "src/" in source else ""
            for used, declared in RUST_USE.findall(text):
                name = used or declared
                base = crate_root if used else os.path.dirname(source) + "/"
                for candidate in (f"{base}{name}.rs", f"{base}{name}/mod.rs"):
                    if candidate in fileset:
                        targets.append(candidate)
                        break
        for target in filter(None, targets):
            a, b = module_of(source, depth), module_of(target, depth)
            if a != b:
                edges[(a, b)] += 1
    return edges


def dependencies(root, files):
    deps = defaultdict(set)
    for f in files:
        name = os.path.basename(f)
        text = read(root, f) if name in {"package.json", "go.mod", "Cargo.toml", "pyproject.toml", "requirements.txt"} else ""
        if name == "package.json":
            try:
                data = json.loads(text)
            except ValueError:
                continue
            for key in ("dependencies", "devDependencies", "peerDependencies"):
                deps[f].update((data.get(key) or {}).keys())
        elif name == "go.mod":
            deps[f].update(re.findall(r"^\s*(?:require\s+)?([\w.\-]+\.[\w.\-]+/[\w.\-/]+)\s+v", text, re.M))
        elif name == "Cargo.toml":
            section = re.search(r"\[dependencies\](.*?)(\n\[|\Z)", text, re.S)
            if section:
                deps[f].update(re.findall(r"^([\w\-]+)\s*=", section.group(1), re.M))
        elif name in ("pyproject.toml", "requirements.txt"):
            deps[f].update(m.lower() for m in re.findall(r"^\s*['\"]?([A-Za-z][\w\-]*)", text, re.M) if m.lower() not in {"name", "version", "description", "requires", "readme"})
    return deps


def entry_points(root, files):
    found = []
    for f in files:
        if re.search(r"(^|/)cmd/[^/]+/main\.go$|(^|/)main\.go$|(^|/)src/main\.rs$|(^|/)src/bin/[^/]+\.rs$|(^|/)__main__\.py$|(^|/)(manage|main|app|wsgi|asgi)\.py$", f):
            found.append(f)
        elif re.search(r"(^|/)(src/)?(index|main|server|app)\.(ts|tsx|js|mjs)$", f) and "/components/" not in f:
            found.append(f)
        elif re.search(r"(^|/)(app|pages|src/pages|src/app|src/routes|routes)/", f) and f.count("/") <= 3 and re.search(r"(page|route|layout|index|\+page|\+server)\.\w+$", f):
            found.append(f)
    for f in files:
        if os.path.basename(f) == "package.json":
            try:
                data = json.loads(read(root, f))
            except ValueError:
                continue
            for key in ("main", "bin"):
                value = data.get(key)
                if isinstance(value, str):
                    found.append(f"{f} -> {key}: {value}")
                elif isinstance(value, dict):
                    found.extend(f"{f} -> bin {k}: {v}" for k, v in value.items())
            for script in ("start", "dev", "serve"):
                if script in (data.get("scripts") or {}):
                    found.append(f"{f} -> scripts.{script}: {data['scripts'][script]}")
    return found


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--depth", type=int, default=0, help="group modules at this many path segments (default: auto)")
    parser.add_argument("--max-edges", type=int, default=60)
    args = parser.parse_args(argv)
    root = os.path.abspath(args.repo)
    if not os.path.isdir(root):
        print(f"Not a directory: {args.repo}", file=sys.stderr)
        return 2
    files = [f for f in list_files(root) if not any(part in SKIP_DIRS for part in f.split("/")[:-1])]
    if not files:
        print("No files found.", file=sys.stderr)
        return 1

    print(f"# Survey of {os.path.basename(root)} ({len(files)} files)\n")

    exts = Counter(os.path.splitext(f)[1] or os.path.basename(f) for f in files)
    print("## Languages (by file extension)")
    print(", ".join(f"{ext} {n}" for ext, n in exts.most_common(10)), "\n")

    print("## Modules (files per module)")
    modules = Counter(module_of(f, args.depth) for f in files)
    for module, n in sorted(modules.items()):
        code = sum(1 for f in files if module_of(f, args.depth) == module and os.path.splitext(f)[1] in CODE_EXT)
        print(f"- {module}: {n} files ({code} code)")
    print()

    manifests = [f for f in files if os.path.basename(f) in MANIFESTS or f.endswith(".tf")]
    print("## Manifests and deploy config")
    print("\n".join(f"- {m}" for m in manifests) or "(none)", "\n")

    print("## Entry points")
    print("\n".join(f"- {e}" for e in entry_points(root, files)[:40]) or "(none found)", "\n")

    print("## External services (from declared dependencies)")
    deps = dependencies(root, files)
    services = defaultdict(set)
    for manifest, names in deps.items():
        for name in names:
            for service, pattern in SERVICE_HINTS.items():
                if re.search(pattern, name):
                    services[service].add(f"{name} ({manifest})")
    for service, evidence in sorted(services.items()):
        print(f"- {service}: {', '.join(sorted(evidence)[:4])}")
    env_examples = [f for f in files if re.search(r"(^|/)\.env\.(example|sample|template)$|(^|/)\.dev\.vars\.example$", f)]
    for env in env_examples:
        keys = re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", read(root, env), re.M)
        if keys:
            print(f"- env keys in {env}: {', '.join(keys[:30])}")
    if not services and not env_examples:
        print("(none detected)")
    print()

    print("## Data model sources")
    testlike = re.compile(r"(^|/)(test|tests|__tests__|fixtures?)/|_test\.\w+$|\.(test|spec)\.\w+$")
    schema = [(f, label) for f in files if not testlike.search(f) for pattern, label in SCHEMA_PATTERNS if re.search(pattern, f)]
    listed = {f for f, _ in schema}
    for f in files:
        if f.endswith(".sql") and f not in listed and not testlike.search(f) and re.search(r"\bcreate\s+table\b", read(root, f, 200_000), re.I):
            schema.append((f, "SQL with CREATE TABLE"))
    seen = set()
    for f, label in schema:
        if f not in seen:
            seen.add(f)
            print(f"- {f} [{label}]")
    if not seen:
        print("(none found: no schema files, migrations, or ORM models)")
    print()

    print("## Internal imports between modules (source -> target: import count)")
    edges = import_edges(root, files, args.depth)
    for (a, b), n in edges.most_common(args.max_edges):
        print(f"- {a} -> {b}: {n}")
    if not edges:
        print("(none resolved: single module, or a language this script doesn't parse)")
    elif len(edges) > args.max_edges:
        print(f"... {len(edges) - args.max_edges} more (raise --max-edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
