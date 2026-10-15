# Image builder

Entrypoint: `python -m crawlops.agent` with `CRAWLOPS_AGENT_KIND=builder`.

The builder downloads bounded source archives through its authenticated API connection and builds in its Docker engine. It also pulls/imports images and runs isolated, network-disabled discovery containers. No uploaded Python or Dockerfile code runs in the API process. The development builder shares the dedicated execution engine; production hostile builds require isolated infrastructure and registry distribution.
