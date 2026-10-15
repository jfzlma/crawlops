# Scrapy telemetry

The initial extension lives inside `apps/api/crawlops/runner.py`. Workers inject that runner via Python command arguments, without installing a CrawlOps package into existing project images. The extension records live counters every five seconds and final stats on spider close. A separately installable extension with push telemetry is deferred; no placeholder package is published.
