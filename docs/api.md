# REST API and agent protocol

Interactive OpenAPI: `/docs`; schema: `/openapi.json`. Frontend, CLI and automation use the same APIs. Send `Authorization: Bearer TOKEN` after authenticating with `POST /api/auth/login` (`email`, `password`). Tokens may be created at `POST /api/tokens` and revoked at `DELETE /api/tokens/{id}`. Secrets and password hashes are never included in public responses.

| Resource | Operations |
| --- | --- |
| Health | `GET /health`, `GET /ready` |
| Identity | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Users (admin) | `GET/POST /api/users` |
| Projects | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}` |
| Source deployment | `POST /api/projects/{id}/deployments/archive` multipart `file`, `version`, JSON `options` |
| Image deployment | `POST /api/projects/{id}/deployments/image` JSON `reference`, `version` |
| Offline image | `POST /api/projects/{id}/deployments/image-archive` multipart `file`, `version` |
| Versions | `GET /api/deployments?project_id=...`, `GET /api/deployments/{id}`, `POST /api/deployments/{id}/activate` |
| Executions | `GET/POST /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/{id}/rerun` |
| Recovery (admin) | `POST /api/jobs/{id}/mark-lost` requires an offline worker |
| Logs | `GET /api/logs/{build\|attempt}/{id}?after=-1`, `/stream`, `/download` |
| Schedules | `GET/POST /api/schedules`, `POST /api/schedules/preview`, `PATCH /api/schedules/{id}?enabled=true` |
| Workers | `GET /api/workers` |
| Environments | `GET/POST /api/environments`; secret values accepted only on creation |
| Registries (admin) | `GET/POST /api/registries`, `DELETE /api/registries/{id}` |
| Audit (admin) | `GET /api/audit` |

List APIs for projects, jobs, deployments, schedules and audit events return `{items, total, offset, limit}` with bounded limits (maximum 200). Jobs filter by `project_id`, `status`, `schedule_id`. Errors use FastAPI's structured `detail` field and HTTP 401/403/404/409/413/422 codes.

## Execution specification

```
{
  "deployment_id": "UUID",
  "spider": "catalog",
  "arguments": {"prefix": "daily"},
  "settings": {"CONCURRENT_REQUESTS": 4, "DOWNLOAD_DELAY": 0.1},
  "environment_id": null,
  "timeout": 3600,
  "memory_mb": 512,
  "cpu": 1,
  "max_retries": 2,
  "retry_delay": 30,
  "criteria": {"min_items": 1, "max_errors": 0}
}
```

`POST /api/jobs` accepts an optional `Idempotency-Key` header. Every run references a READY deployment and one of that version's discovered spiders. Settings overrides have an explicit allowlist; Python code/module loading settings are rejected. `max_retries` concerns failed **executions**, with new attempt records and exponential backoff. An agent reconnecting or retrying a callback resumes the same attempt and does not consume an execution retry.

A schedule adds `name`, either a five-field `cron` or future timezone-aware `run_at`, IANA `timezone`, `overlap` (`forbid` or `allow`), `misfire` (`skip` or `catch_up`) and `max_concurrent`. The next five cron occurrences are previewable without creating records. Skip ignores occurrences more than 60 seconds late; catch-up processes one stored occurrence each tick. Overlap-blocked occurrences are advanced/skipped. One-time schedules disable after consideration.

## Logs and telemetry

Build ID is returned in deployment detail; attempt IDs in job detail. Chunk `sequence` is monotonically increasing per stream. Poll with `after=last_sequence`; duplicates are ignored on append. SSE `/stream` emits IDs and a terminal `complete` event; use authenticated fetch streaming, since native browser EventSource cannot set bearer headers. The frontend uses offset-based polling, pause/resume, search, level filtering, and download. The visible tail caps at 3,000 chunks; download retrieves the full retained archive.

The project runner injects a Scrapy extension in memory and emits live/final stats through stdout. No project source changes are required. It disables the Telnet console, applies settings, runs the selected spider, and exits nonzero if startup fails or close reason is not `finished`. Container exit code plus final statistics and success criteria determine terminal status.

## Agent endpoints

`/internal/*` requires the separately configured `CRAWLOPS_AGENT_TOKEN`. These routes are intentionally not proxied by the supplied web ingress. Agents need private network reachability to the API.

* `POST /internal/heartbeat` registers stable name/kind, engine availability and capacity.
* Builder claims via `POST /internal/builds/claim?agent_id=NAME`; downloads archive, appends sequenced logs, and reports immutable image ID, engine ID, digest and discovered names at `/complete`.
* Worker claims via `POST /internal/jobs/claim?host_id=UUID`; receives job, attempt, immutable image, decrypted runtime environment, and configured redactions.
* Attempt `/update`, `/log`, `/complete`, and control `GET /internal/attempts/{id}` require the owning host ID. Callback commits are transactional and terminal completion is idempotent.
* Scheduler calls `/internal/scheduler/tick`; atomic PostgreSQL claims create jobs with unique schedule occurrence keys. `/internal/maintenance` applies retention.

Agents are trusted principals in this MVP. A shared bearer secret is not multi-tenant isolation; use protected TLS transport and private networking.
