# Execution worker

Entrypoint: `python -m crawlops.agent` with `CRAWLOPS_AGENT_KIND=worker`.

The shared implementation lives in `apps/api/crawlops/agent.py` to reuse the job protocol and runner without duplicating Python distributions. The worker process has Docker TLS credentials and no database credentials. It initiates outbound API requests, maintains heartbeats, reconciles stable named containers, archives logs/stats, enforces resource limits, and leaves containers running across worker/API restarts.
