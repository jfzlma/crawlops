# Operating CrawlOps

## Start and validate

Prerequisites: Docker Engine with Compose v2, enough disk space for images, and roughly 4 GB available memory. The development engine is a privileged Docker-in-Docker service; install only on a trusted development host. Never expose its ports or the internal agent API publicly.

```
make init
make up
make examples
```

Open http://localhost:8080. Sign in as `admin@crawlops.local` with `CRAWLOPS_ADMIN_PASSWORD` from `.env`. Create a project, select Deploy project → Project archive, and upload `data/examples/simple-spider.zip`. Watch build logs, wait for READY, activate, and run `catalog`. It reads a bundled HTML fixture and returns three items without public web access. Rerun with `{"prefix":"second"}`. The custom-dependencies example uses Babel and custom Scrapy settings.

Test real Docker operations with:

```
python -m pip install -e '.[dev]'
python infrastructure/acceptance.py --restart
```

The test creates real records, builds a real Docker image, discovers spiders, executes two crawls, checks logs and statistics, imports an existing image, executes a one-time schedule, and restarts worker/API/dashboard/scheduler. It fails on real errors and leaves history for inspection. It requires preloaded base images or build access to a package index. This test must pass on the target host before calling the MVP end-to-end verified.

## Local development

```
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
make init
alembic upgrade head
uvicorn crawlops.main:app --reload
```

The default database is SQLite for unit tests and single-process API development only. Compose uses PostgreSQL; production queue and schedule concurrency require PostgreSQL row locks. In another terminal: `cd apps/web && npm ci && npm run dev`. Vite proxies API traffic to localhost:8000. Start agents separately with `DOCKER_HOST`, `CRAWLOPS_AGENT_TOKEN`, `CRAWLOPS_API_URL`, `CRAWLOPS_AGENT_NAME`, and `CRAWLOPS_AGENT_KIND`. Agent names must be stable and unique; run one process per name. To use Compose's API from external agents, put it behind a private TLS reverse proxy rather than publishing internal Docker ports.

## Persistence and backup

Back up PostgreSQL, `/data`, the encryption key, and engine image storage consistently. Compose named volumes retain history through ordinary `down` and service restarts. `docker compose down -v` destroys these volumes. Without the encryption key, environment secrets, registry passwords, and saved build arguments cannot be decrypted. Rotating that key requires explicit decrypt-and-reencrypt migration; changing `.env` alone loses access to encrypted values.

PostgreSQL stores append-only logs. The scheduler runs retention hourly: completed-attempt and terminal-build logs older than 30 days are removed, terminal build source archives after 7 days, and heartbeat history after 7 days. Active logs are retained. Set `CRAWLOPS_LOG_RETENTION_DAYS` and `CRAWLOPS_SOURCE_RETENTION_DAYS` in the API environment to change retention. Job metadata, artifacts, statistics and audits are retained. Image garbage collection is an explicit operator task; do not prune images needed by historical pinned deployments.

## Partial failures

| Failure | Behavior |
| --- | --- |
| API / dashboard restart | Containers continue in Docker. Agents reconnect; SQL history and log offsets survive. |
| Scheduler restart | SQL `next_run_at` survives. Claims and unique occurrence creation commit in one transaction. |
| Worker restart | Same stable host resumes its unfinished attempt and named container. It does not blindly launch a new attempt. |
| Control-plane network interruption | Container continues; logs remain in Docker until reconnect. Scrapy close timeout still runs inside the project container. |
| Redis interruption | No work is lost: SQL polling is the implemented dispatch mechanism. Redis is provisioned for future wake-up optimization. |
| Docker outage | Ownership remains with the worker, which retries reconciliation after the daemon returns. |
| Permanently missing container | Attempt becomes LOST rather than successful. Operator can rerun explicitly. |
| Permanently missing worker | Offline after 45 seconds. Admin may mark its attempt LOST after 60 seconds, then rerun. A returning worker respects terminal ownership and removes its old container. |
| Build agent restart | Same agent resumes its build; an already-built deterministic image tag is reused and validated. Build logs append from the previous sequence. |
| Cancellation during completion | API locks the job; cancellation wins if already recorded. Completion of a terminal attempt is idempotent. |

Do not rerun LOST jobs until the disconnected host has been fenced if duplicate external side effects would be harmful. CrawlOps does not promise exactly-once crawler side effects.

## Registries, offline installations, and corporate networks

Register encrypted credentials with `POST /api/registries` (admin). Registry hostname must match the image reference, including a port if present; use `docker.io` for Docker Hub. Agents receive credentials only for the relevant pull. Local images can be referenced by content ID. The execution host must share the builder's engine for local image IDs; cross-engine image distribution is deferred.

The deployment wizard also imports uncompressed `docker save` TAR archives containing exactly one image, up to 512 MB. Only the agent's Docker engine loads layers. For larger imports, an operator may load the image into the private execution engine and deploy its image reference.

Source builds accept `PIP_INDEX_URL`, `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` build arguments through the API/UI. These are encrypted in database storage, but Docker build arguments can appear in image history: use short-lived credentials and a custom Dockerfile with a secure build mechanism for sensitive package authentication. Credentials in project files are the project's responsibility. Custom Dockerfiles are supported. `pyproject.toml` projects install using pip's PEP 517 backend, including poetry-core; Poetry lockfile installation is deferred.

For air-gapped hosts, mirror/preload platform images, Python base images, Python wheels, and npm dependencies before building. Build the platform images on an approved build machine and transfer with Docker save/load; keep your internal package indexes reachable from the execution engine. There are no mandatory SaaS connections, public-site fixtures, or telemetry. Custom CAs require installing the corporate CA into platform and project base images. OS package installation and Git are never required to deploy an existing image.

## Production deployment

Use TLS at the ingress, restrict operator access to a corporate network, and configure backups before real use. Use dedicated build and execution machines with a common trusted registry before accepting untrusted tenants. The supplied Compose arrangement intentionally uses a single engine and is a development/operator-controlled MVP, not hardened multi-tenant infrastructure. Add resource limits to platform services based on build sizes; execution containers already receive CPU, memory, PID, non-root, capability-drop and no-new-privileges controls.

## Docker engine TLS hostname recovery

If agents log `certificate verify failed: Hostname mismatch, certificate is not valid for 'engine'`, recreate the engine with the configured `hostname: engine` and `DOCKER_TLS_SAN: DNS:engine`. These ensure its generated certificate matches `DOCKER_HOST=tcp://engine:2376`. Keep certificate verification enabled.

```
docker compose stop worker builder
docker compose up -d --force-recreate engine
docker compose up -d --force-recreate worker builder
docker compose logs --follow --tail=30 worker builder
```

The engine's image data and database volumes are retained. Recreating the engine interrupts any active containers, so apply this recovery while no crawls are running. Agent recreation reloads the regenerated client certificates. Queued deployment builds remain in PostgreSQL and will be claimed after connectivity returns. Check **Workers** for both agents to come online.
