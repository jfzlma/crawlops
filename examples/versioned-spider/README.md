# Versioned deployment sample

This deterministic Scrapy project reads bundled HTML without internet access.
Version v1 yields Notebook, Pencil, and Backpack. The verification script creates
an updated v2 archive that adds Eraser and labels every item with v2.

Both versions write `/tmp/.output/items.jsonl`, read it back, and log the exact
saved records as `SAMPLE_RESULT`. Output files are temporary; the log provides
verification evidence retained by CrawlOps.

The sample disables Scrapy's optional remote-control extension, which otherwise
tries to create job metadata under the non-root user's home directory on recent
Scrapy versions. That location is read-only in CrawlOps.

From the CrawlOps repository root, with the API running:

```sh
.venv/bin/python infrastructure/verify_versions.py --url http://localhost:8080
```

The script prompts for the administrator password, or accepts `CRAWLOPS_TOKEN`
or `CRAWLOPS_PASSWORD` from the environment. Set `CRAWLOPS_ADMIN_EMAIL` if needed.
It creates a separate project, uploads and activates v1, checks its real run,
then uploads and activates v2 and checks the changed results. Finally it runs
explicitly pinned v1 again to verify the old deployment remains unchanged while
v2 stays active. It checks exact records, item counts, zero Scrapy errors, and
real container IDs.

Archives, build logs, execution logs, and `results.json` are saved under
`data/version-verification` (override with `--output`). PASS is recorded only
after all server checks succeed. Project/deployment/job history is retained for
inspection. The source here remains v1; the generated v2 archive contains the
actual updated Python source.
