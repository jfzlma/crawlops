# CrawlOps architecture and delivery plan

CrawlOps separates a FastAPI control plane from outbound-polling builder and execution agents. PostgreSQL is authoritative for projects, immutable deployments, discovered spiders, jobs, attempts, schedules, logs and audit events. Redis is an optional wake-up accelerator; loss of Redis never loses work. React consumes the same documented REST API as the CLI. The API never holds Docker credentials or starts crawler processes.

## Decisions

* Transactional `FOR UPDATE SKIP LOCKED` claims and unique schedule-occurrence keys provide at-least-once dispatch with idempotent ownership. Agent IDs persist across restarts. Container names derive from attempt IDs; workers reconcile named containers before creating one. Scheduler claims and occurrence creation commit atomically.
* Image IDs (local content-addressed OCI artifacts) pin executions on the MVP's single Docker engine. Registry digests are retained when available. Multiple engines require a common registry and authenticated image distribution; arbitrary multi-host placement is deferred.
* Builder is a separate process using a disposable build context. The development Compose stack uses a dedicated Docker-in-Docker engine, never the workstation socket. Build and execution agents share that engine in the single-host MVP. Production must isolate untrusted builds on dedicated hosts and use a registry. A Docker build sandbox is not a multi-tenant security boundary.
* Append-only SQL log chunks survive container deletion and support offset-based reconnect. A storage interface makes migration to object storage possible. SQL logs are appropriate for the first release, not unlimited ingest.
* Scrapy runs through an injected Python runner without modifying project source. The runner writes final stats and injects a signal extension for live stats. Existing images need Python and Scrapy, a correct working directory, and must allow Python as the entrypoint.
* Persistent UTC times and IANA zones govern cron calculation. Catch-up emits one occurrence at a time; skip advances to the next future occurrence. `forbid` overlap counts nonterminal jobs. Logical execution retry is distinct from reclaiming interrupted dispatch.

## Milestones and validation gates

1. Core: schema + migrations; authenticated project APIs; safe archive upload; builder claim/build/discovery; immutable image registration; executor claim/run/reconcile; durable logs/stats; connected React workflows. Test archive attacks, authorization, deployment ownership, job transitions and API CRUD. Build frontend.
2. Scheduling: persisted cron and one-shot schedules, timezone preview, overlap and max concurrency, unique occurrences, retries, timeout/cancel. Test restart persistence and duplicate dispatch.
3. Agent reliability: authenticated outbound claims, heartbeat, startup reconciliation, container naming, callback ownership. Test stale ownership and restart claims. Single-engine placement remains explicit.
4. Usability: CLI, local fixture spiders, operator/security docs. Advanced integrations remain documented limitations rather than fake UI.

## Risks

Docker access grants engine-level control; agents are trusted infrastructure. Uploaded source is executable code. Persistent Postgres and engine volumes are required. A disconnected worker cannot immediately receive cancellation; it checks on reconnect. Logs can contain project-generated secrets; CrawlOps redacts configured secrets, but cannot infer arbitrary credentials printed by user code. API writes and agent callbacks must be transactional. Docker end-to-end verification requires a reachable daemon; tests using fakes never substitute for that acceptance gate.
