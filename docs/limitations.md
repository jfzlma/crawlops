# Release scope and verification

Implemented: authenticated API, workspace roles and user creation, project CRUD, ZIP/TAR source deployment, generated/custom Dockerfiles, PEP 517 dependencies, encrypted build arguments, existing local/registry image validation, encrypted registry credentials, offline Docker save import, version-aware spider discovery, immutable artifacts, activation/rollback by reactivation, Docker execution, injected live/final Scrapy stats, durable log chunks/stream/download, cancellation, timeouts, bounded retries, attempt history, cron/one-time schedules, timezone preview, overlap/max concurrency, missed occurrence policy, outbound agents, heartbeats, same-host reconciliation, retention, CLI, real connected React workflows and deterministic examples.

This is an initial single-engine MVP implementation, not completion of all four proposed phases. Production acceptance requires the real Docker test on a suitable host. The implementation environment denied Docker socket access and external package downloads; backend tests, actual Scrapy file-fixture execution, frontend tests/type-check/build, migration checks and Compose validation can be run independently. No simulated crawler or seed dashboard data ships in the application.

Deferred:

* Distributed placement across separate engines, authenticated image push/pull distribution and host pools. Multiple registered workers are supported only when sharing the same engine; stable per-agent ownership is implemented. Capacity checks are basic; one slot per worker.
* Git/webhooks, Poetry lockfile fidelity, Python versions other than 3.12/3.13, registry build-secret mounts, OCI-layout image archive formats, arbitrary writable mounts, per-project network policy.
* Automated stalled-crawl rules, notifications, Loki/Prometheus, SSO, project-level ACLs, per-agent identities, token scopes, full audit-report exports.
* Object-store log backend and unlimited-throughput ingestion. Initial SQL logs and full Docker-log polling are bounded by daemon retention (100 MB per container) during control-plane outages. Long or very chatty runs can overrun that buffer; use external durable logging before such workloads.
* BuildKit-native remote build service (current builder uses Docker SDK build API), configurable parallel build slots, automatic image garbage collection, and failed-build retry UI.
* Detailed CPU percentage/rate charts and aggregate item throughput; raw CPU counter, memory and live Scrapy counters are available per attempt. Overview charts execution outcomes from the most recent 200 jobs, not fabricated throughput.
* Advanced table/editor widgets: the current frontend uses accessible custom CSS/components, regular tables, and a searchable log viewer rather than Tailwind/shadcn, TanStack Table, or Monaco. Branding is centralized in the app shell/title and CSS variables.
* Cron editing after creation (enable/disable is available); create a replacement schedule to change the expression. Overlap-blocked occurrences are skipped, not queued for later.
* Exactly-once crawler side effects: claim idempotency protects container creation, but a crashed host and an explicit rerun may still repeat external actions. Fence unreachable hosts before rerunning critical jobs.

Unit tests use SQLite and API-level agent fixtures; they do not validate PostgreSQL locking semantics or replace a real daemon test. Run the acceptance script and concurrency checks against PostgreSQL/Docker before production deployment. No browser automation or cross-browser visual review has been performed in the restricted implementation environment.
