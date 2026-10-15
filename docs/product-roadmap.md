# Public self-hosted release

CrawlOps targets teams running their own Scrapy deployments on infrastructure
controlled by trusted operators. The current single-engine architecture is the
starting point. A hosted service for untrusted customers needs separate design
and isolation work.

## Release foundation

Implemented in the current source:

- Backend, frontend, and PostgreSQL migration CI workflows.
- A manually triggered Docker acceptance workflow covering restart behavior and
  source deployment updates, with version verification artifacts retained.
- Human-readable attempt failure reasons when a process exits successfully but
  misses item or error criteria.
- Runtime disabling of Scrapy's optional remote-control HTTP server to prevent
  writes outside the writable runtime directory.
- Local image upload documentation and a deterministic v1/v2 sample.
- Exclusion of local credentials, database files, logs, build output, and generated
  verification evidence from Git.

The workflows must pass on the published repository before release. Merely adding
workflow definitions does not establish that PostgreSQL or Docker checks passed.

## First product milestone: usable run outputs

Persist output files per execution attempt and provide authenticated file listing
and downloads in the API and dashboard. Keep each attempt isolated, bound file
counts and total bytes, reject links and path traversal, and define retention and
cleanup. Users should see output location and retention before starting a run.
Temporary `/tmp` files currently disappear with the container; the MVP does not
provide this capability.

Acceptance: upload a spider that produces a JSONL feed, run two versions, download
and verify both outputs after container removal, and confirm a user without access
cannot retrieve them. Document upgrade and backup implications.

## Release blockers

- Run CI on clean installations and the Docker acceptance workflow on supported
  hosts. Add simultaneous PostgreSQL claim and schedule tests, outage recovery,
  and upgrade/rollback exercises before asserting production reliability.
- Define supported host architectures, operating systems, dependency versions,
  upgrade policy, and resource sizing. Validate a fresh install and an upgrade
  using those documented configurations.
- Add login abuse protection, review token lifecycle and secret handling, and
  complete a security review of archive/image ingestion and download endpoints.
- Exercise backup and restore of the database, encryption key, source data,
  execution images, and future output storage; publish the tested procedure.
- Perform browser accessibility and responsive layout review for deployment,
  failure investigation, scheduling, and output retrieval workflows.
- Publish versioned release notes, supported limitations, issue templates, and
  contribution instructions. Tag a release only after the acceptance evidence
  and remaining limitations have been reviewed.

## Later capabilities

Git deployments and webhooks, notifications, metrics export, project-level access
control, SSO, independent agent credentials, multi-engine placement, and registry
image distribution should follow validated user needs. They are not included in
the initial public self-hosted release promise.
