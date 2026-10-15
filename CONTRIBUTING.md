# Contributing

Use Python 3.12 and Node.js 22 for the same baseline as CI.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check apps/api tests infrastructure/verify_versions.py examples/versioned-spider
cd apps/web
npm run check:lock
npm ci
npm test
npm run build
```

Read [architecture](docs/architecture.md), [security](docs/security.md), and the
[product roadmap](docs/product-roadmap.md) before changes that affect execution,
authentication, persistence, or scheduling. Include migrations for schema changes
and regression tests for behavior changes. Never commit credentials, local
runtime data, or logs from real workloads.

For Docker validation, follow the README setup and run
`python infrastructure/acceptance.py --restart` followed by
`python infrastructure/verify_versions.py`. These create project/job history;
use a dedicated development installation. Unit tests are not a substitute for
Docker or PostgreSQL validation.

Report bugs with reproduction steps, versions, expected behavior, and redacted
logs. Report suspected vulnerabilities privately to the repository maintainer
rather than posting credentials or exploit details in a public issue.
