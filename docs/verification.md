# Implementation verification

## Operator-confirmed version deployment check (2026-10-15)

The operator ran `infrastructure/verify_versions.py` against the local Docker
installation and supplied a PASS result for project
`7634de1b-1f40-4eb5-bbc0-317cbdb122f5`. Source v1 returned three exact items,
updated v2 returned four, and a pinned v1 run after v2 activation still returned
the original three. Each run verified temporary output file read-back and zero
Scrapy errors. v2 remained active. This verifies that specific versioned source
deployment flow; it does not establish that the broader restart, PostgreSQL
concurrency, browser, or local image TAR upload checks passed.

The release foundation adds CI definitions for backend/frontend checks and real
PostgreSQL migrations, plus a manual Docker acceptance workflow. Those workflows
have not yet run on GitHub. The runtime now disables Scrapy's optional remote
control extension for all jobs; this change requires rebuilding the worker image.

## Earlier implementation checks

Executed in the restricted workspace:

* 33 pytest tests passed, including API CRUD, authentication/RBAC, archive attacks, immutable deployment discovery/activation, execution claims and same-host restart reconciliation, durable/idempotent callbacks and logs, retries/cancellation, schedule restart persistence/overlap, registry credentials, environment secret redaction, retention, CLI-to-API workflows, and two real Scrapy fixture runs.
* 8 Vitest workflow tests passed: login, connected project records, errors, deployment source selection, run specification, log filtering/pause, schedule toggle and cron preview.
* TypeScript check and Vite production build passed. The Recharts chunk is approximately 384 KB minified and is split from the application/vendor chunks.
* Ruff checks passed. Python modules compiled.
* Alembic upgrades and metadata drift checks passed against SQLite.
* Docker Compose configuration validated.
* npm lockfile dry-run validation passed offline. Fresh package retrieval could not run because external DNS/network access was denied. Local validation used cached package distributions; package manifests and lockfile contain registry dependencies, not paths to unrelated workspace projects.

Not verified here:

* Actual Docker image build/container execution, Compose startup/restarts, and TLS engine connectivity: the host Docker socket is outside this task's permitted access. Run `python infrastructure/acceptance.py --restart` on the target Docker-capable host.
* PostgreSQL row-lock/concurrency behavior under simultaneous schedulers and workers, migration upgrade against real PostgreSQL, load tests and failure injection.
* Browser visual QA/cross-browser accessibility and responsiveness. Component tests and compilation are not visual browser checks.

The real Scrapy tests execute the injected runner against the bundled HTML files and assert three items, successful finish, and zero Scrapy errors. They are not Docker tests. SQLite/API fixtures never substitute for the Docker/PostgreSQL acceptance gate.

## Frontend container install correction

The Docker build exposed `Missing: esbuild@0.28.2 from lock file`. The earlier Vite 5 application toolchain and Vitest 4's nested Vite 8 produced an unresolved optional esbuild peer. Validation against the populated development directory did not catch the resolution performed by the clean Docker install.

The application now pins Vite 8.1.4 with React plugin 6.0.3, sharing Vite with Vitest 4.1.10. The lockfile was normalized with npm in an empty directory, removing the conflicting esbuild tree. Chunk configuration now uses Rolldown's codeSplitting API. Production compilation and all eight frontend workflow tests pass.

`cd apps/web && npm run check:lock` checks the lock from a temporary directory without node_modules for Linux ARM64 and x64. Both pass without peer-resolution warnings. A full offline installation proceeds past lock validation but cannot download the uncached Vite tarball in this restricted environment. Actual Docker image building still requires host Docker access.
