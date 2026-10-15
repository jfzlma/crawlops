# CrawlOps

**Container-native operations for Scrapy.** Deploy source archives or OCI images, discover spiders, run isolated containers, inspect durable logs and Scrapy statistics, and schedule recurring crawls on infrastructure you control.

CrawlOps is an open-source, self-hosted initial MVP. The API and dashboard never run spiders or access a Docker socket. A separate builder builds images; an outbound-connected worker runs disposable containers. PostgreSQL owns deployment versions, execution attempts, schedules, logs, and audit history.

## Run

Requirements: Docker Engine + Compose v2, Python 3 for credential generation, approximately 4 GB available memory.

```sh
cd crawlops
make init
make up
make examples
```

Open **http://localhost:8080**. Sign in with `admin@crawlops.local` and the generated `CRAWLOPS_ADMIN_PASSWORD` in `.env`.

1. Create a project.
2. Select **Deploy project → Project archive** and upload `data/examples/simple-spider.zip`.
3. Watch build output and spider discovery; wait for READY.
4. Activate the deployment, then run `catalog`.
5. Inspect logs, three scraped fixture items, final Scrapy statistics, and attempt history.
6. Run again with arguments `{"prefix":"second"}`.
7. Register an existing image or import a `docker save` TAR through the deployment wizard.
8. Create a cron or one-time schedule with its deployment pinned.

The first build needs a Python base image and Python dependencies, either via internet or internal/preloaded mirrors. The example crawl itself requires no network. Custom-dependencies demonstrates Babel and Scrapy settings. Source builds detect nested `scrapy.cfg`, `requirements.txt`, or a PEP 517 `pyproject.toml`; custom Dockerfiles are respected.

## Build and upload a local project image

Place a `Dockerfile` in your Scrapy project directory, beside `scrapy.cfg`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN python -m pip install --no-cache-dir "scrapy>=2.12,<3"
# Uncomment if your project has requirements.txt:
# RUN python -m pip install --no-cache-dir -r requirements.txt

RUN chmod -R a+rX /app
USER 65532:65532

ENTRYPOINT []
CMD ["scrapy", "list"]
```

Add a `.dockerignore` beside it to exclude local credentials, environments, and output:

```text
.git
.env
.env.*
.venv
venv
__pycache__
.output
*.pem
*.key
*.tar
```

From that directory, build the image, check spider discovery under the runtime restrictions, and export it:

```sh
docker build -t my-spider:v1 .
docker run --rm --read-only --tmpfs /tmp \
  --user 65532:65532 --network none \
  --entrypoint python my-spider:v1 -m scrapy list
docker save -o my-spider-v1.tar my-spider:v1
```

The discovery command should print your spider names. Build for the same CPU architecture as the CrawlOps execution host. The image must include Python, Scrapy, and your project's dependencies, with its working directory set to the directory containing `scrapy.cfg`.

In the dashboard:

1. Open your project and select **Deploy project**.
2. Select **Air-gapped? Import a Docker image archive**.
3. Upload `my-spider-v1.tar`, enter a version, and submit the deployment.
4. Wait for **READY**, activate the deployment, then run your spider.

The upload accepts an **uncompressed `docker save` TAR containing exactly one image, up to 512 MB**. CrawlOps uses a separate Docker engine, so images built in your host's local Docker engine must be transferred through this upload or made available through a registry.

### Spider output directories

Spider containers run as UID/GID `65532:65532` with a **read-only filesystem**. Only `/tmp` is writable; writing to a project-relative directory such as `/app/.output` will fail even if the Dockerfile grants write permissions.

Configure temporary files to use `/tmp/.output` and have your spider create that directory before writing. For example, Scrapy feed output can use `/tmp/.output/items.jsonl` after the directory is created. These files are temporary and are lost when the container is removed; CrawlOps does not currently provide persistent file output or file downloads. Send output that must survive the run to an external storage service or database. See [runtime security](docs/security.md) for more details.

## CLI

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
crawlop login
# Store the returned token in CRAWLOPS_TOKEN.
crawlop projects create catalog
crawlop deploy ./examples/simple-spider --project catalog --version v1
# Activate a READY deployment through the dashboard/API.
crawlop spiders list catalog
crawlop run catalog catalog --args '{"prefix":"cli"}'
crawlop jobs list
crawlop jobs logs JOB_ID --follow
crawlop jobs cancel JOB_ID
crawlop deploy-image registry.internal/crawler:1.2 --project catalog --version v2
crawlop schedules list
```

## Validate

```sh
pytest -q
ruff check apps/api tests
cd apps/web && npm run check:lock && npm ci && npm test && npm run build
```

With Compose running, `python infrastructure/acceptance.py --restart` exercises real image builds, discovery, containers, logs, stats, existing-image deployment, one-time scheduling and service restarts. This is the Docker acceptance gate; API fixture tests alone do not establish end-to-end correctness.

Implementation checks: 33 Python tests and 8 frontend tests passed, including actual Scrapy fixture runs; frontend type-check/production build and Alembic schema checks passed. Docker access was denied in the implementation environment, so the integrated Compose workflow remains unverified. See [release scope](docs/limitations.md) before evaluating production use.

## Repository

```text
apps/api/crawlops/       FastAPI, models, services, CLI, agent and scheduler entrypoints
apps/web/               React + TypeScript + Vite dashboard
apps/{builder,worker,scheduler}/  Component boundary notes
migrations/             Versioned Alembic schema
examples/               Deterministic minimal and additional-dependency Scrapy projects
infrastructure/         Dockerfiles, reverse proxy, init, acceptance and fixture packaging
packages/               CLI and telemetry boundary notes
tests/                  API, archive, lifecycle and real Scrapy integration tests
docs/                   Architecture, API, operations, security and release scope
```

Builder, worker and scheduler use one Python distribution to keep the MVP maintainable; they run as separate services with different credentials and privileges. Redis is included but SQL polling is the implemented durable queue; it is not a second source of truth.

## Documentation

* [Architecture, decisions, risks, and milestones](docs/architecture.md)
* [API and agent protocol](docs/api.md) · interactive OpenAPI at `/docs`
* [Deployment and operations](docs/operations.md)
* [Security model](docs/security.md)
* [Known limitations and deferred features](docs/limitations.md)
* [Public self-hosted product roadmap](docs/product-roadmap.md)
* [Contributing and development checks](CONTRIBUTING.md)

The Compose engine is privileged Docker-in-Docker, isolated from the host socket and not published. This arrangement is for trusted operator-controlled deployments. Dedicated build infrastructure and a shared registry are required before hostile multi-tenant use. Multi-engine distribution, Git integration, alert notifications, SSO and advanced observability remain deferred.

MIT licensed. No mandatory SaaS, external telemetry, or public website dependency.
