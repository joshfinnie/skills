# Review checklist

Questions to put to every branch, grouped by lens. Skip a lens only after deciding it doesn't apply.

## Contents

- Correctness
- System connections
- Security
- Data and migrations
- Performance and scale
- Reliability and operability
- Tests
- Design and maintainability
- Whole-repo reviews

## Correctness

- Does the code do what the intent says, for the normal case and the edges: empty, one, many, maximum, duplicate, missing, malformed?
- Off-by-one errors, inclusive and exclusive bounds, time zones and DST, and integer overflow and rounding.
- Every error path: is the error handled, returned, or swallowed? Does a failure halfway through leave partial state behind?
- Null, undefined, and zero values. Does the branch assume a field that's optional?
- Concurrency: shared state, check-then-act races, goroutines or promises nobody awaits, and missing locks or transactions around multi-step writes.
- Resource lifetimes: unclosed files, rows, connections, and subscriptions, and listeners that never get removed.

## System connections

- **Callers.** For every changed function, method, or type, does each caller still get what it expects? Changed return shapes, new error cases, new side effects, and changed defaults all count.
- **Contracts across a process boundary.** API routes, request and response fields, status codes, event payloads, and queue messages. Who consumes them (frontend, mobile, other services, public API users, the OpenAPI spec, generated SDKs)? Renamed or removed fields break consumers silently when their code falls back to a default (`user.displayName || user.username`).
- **Rollout compatibility.** During a deploy, old and new code run side by side, and old clients keep calling the new server. Is the change safe in both directions? Does it need a two-step (expand, then contract) rollout?
- **Shared state.** Database tables, caches, files, and feature flags that other code reads. Does this change what they contain or mean?
- **Background work.** Cron jobs, workers, firehose and stream consumers, and backfill scripts that run the same code paths without a request.
- **Config.** New env vars: are they set in every environment, documented in `.env.example`, and given a safe default? Removed ones: is anything still reading them?
- **Docs and specs** that describe the old behavior and are now wrong.

## Security

- Authentication: is every new route or action behind the right check?
- Authorization: does every read and write scope by owner or tenant, the way the rest of the codebase does? An ID from the client is not proof of ownership (IDOR).
- Input: validated and size-limited at the boundary? Any SQL, shell, path, template, or HTML built from user input?
- Secrets and personal data: anything new in logs, error messages, URLs, client bundles, or analytics?
- Server actions, webhooks, and callbacks: CSRF, signature verification, and replay.
- Dependencies: new packages that are unmaintained, typosquatted, or far heavier than the job needs.

## Data and migrations

- How does this project apply migrations: once and tracked, or re-run on every boot? Is the new migration safe under that model (idempotent, `IF EXISTS`, `IF NOT EXISTS`)? Do older migrations still run cleanly after this one?
- Is it reversible? If not, is the data loss intended, announced, and backed up?
- Locking: will `ALTER TABLE` or a new index lock a large table? Is a concurrent index or a batched backfill needed?
- Deploy order: can the old app run against the new schema, and the new app against the old one?
- Every query, view, trigger, and index that references a changed column or table, including ones outside the diff.
- Hard versus soft deletes: what references the deleted rows without a foreign key (by URI, ID string, or cache key), and what happens to those references now?

## Performance and scale

- N+1 queries, queries inside loops, and missing indexes for new `WHERE` or `ORDER BY` clauses.
- Unbounded reads: no `LIMIT`, loading whole tables or files into memory, pagination that can't scale.
- Hot paths: is new work added to every request, render, or event?
- Payload sizes, re-renders, and bundle size on the frontend.
- Timeouts and retries on outbound calls, and what happens under a slow or failing dependency.

## Reliability and operability

- When this fails in production, how will anyone know? Logs with enough context, metrics, alerts.
- Retries: are the retried operations idempotent?
- Partial failure: is a multi-step operation (write to the database, then call an external API) consistent if step two fails?
- Feature flags or a kill switch for risky behavior. Is there a rollback plan, and does the migration allow one?

## Tests

- Do the tests exercise the behavior that changed, or only that the code runs? Would they fail if the implementation were wrong?
- Missing cases: the error path, the boundary, the authorization failure (another user's ID), the empty state.
- Tests that assert on implementation details or copies of constants instead of behavior.
- Flakiness: real time, randomness, network, ordering, and shared state between tests.
- Did the existing suite actually run against this change? Run it if you can.

## Design and maintainability

- Is this the right layer for the change, and does it follow the patterns the codebase already uses for the same problem?
- Duplication of logic that exists elsewhere. Dead code left behind or newly created.
- Names that say what things are, and abstractions that earn their complexity.
- Will the next person to touch this understand it without the author in the room?
- Scope: does the branch do one thing, or does it bundle unrelated changes that should ship separately?

## Whole-repo reviews

- Architecture: do the module boundaries match the way the code actually depends on itself? Any cycles, god modules, or layers that leak?
- The riskiest paths (auth, payments, user data, deletes): read them end to end.
- Hotspots: files that change often and are large are where bugs concentrate. Read the top few closely.
- Test coverage by module: which important modules have none?
- Operational readiness: CI that runs tests, a deploy that can roll back, migrations that are safe to re-run, config that's documented.
- Dependency health: outdated or abandoned packages, and pinned versions with known problems.
- Consistency: the same problem solved three different ways across the codebase.
