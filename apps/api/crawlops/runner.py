"""Executed inside project images via python -c; only stdlib and Scrapy are required."""

import json
import os
import sys
from datetime import date, datetime


def main():
    from scrapy import signals
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from twisted.internet.task import LoopingCall

    def serialize(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)

    class Telemetry:
        @classmethod
        def from_crawler(cls, crawler):
            obj = cls()
            obj.crawler = crawler
            crawler.signals.connect(obj.opened, signal=signals.spider_opened)
            crawler.signals.connect(obj.closed, signal=signals.spider_closed)
            return obj

        def emit(self):
            print(
                "__CRAWLOPS_STATS__" + json.dumps(self.crawler.stats.get_stats(), default=serialize),
                flush=True,
            )

        def opened(self, spider):
            self.loop = LoopingCall(self.emit)
            self.loop.start(5, now=False)

        def closed(self, spider, reason):
            if getattr(self, "loop", None) and self.loop.running:
                self.loop.stop()
            self.emit()

    # Scrapy load_object resolves __main__.Telemetry.
    globals()["Telemetry"] = Telemetry
    spec = json.loads(os.environ["CRAWLOPS_SPEC"])
    settings = get_project_settings()
    settings.setdict(spec.get("settings", {}), priority="cmdline")
    settings.set("TELNETCONSOLE_ENABLED", False, priority="cmdline")
    if spec.get("timeout"):
        settings.set("CLOSESPIDER_TIMEOUT", spec["timeout"], priority="cmdline")
    extensions = dict(settings.getdict("EXTENSIONS"))
    # Recent Scrapy versions enable an HTTP control server that writes state
    # outside /tmp. CrawlOps owns cancellation and telemetry for isolated runs.
    extensions["scrapy.extensions.remote_control.RemoteControl"] = None
    extensions["__main__.Telemetry"] = 999
    settings.set("EXTENSIONS", extensions, priority="cmdline")
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(spec["spider"])
    errors = []
    task = process.crawl(crawler, **spec.get("arguments", {}))
    task.addErrback(lambda failure: errors.append(str(failure)))
    process.start()
    stats = crawler.stats.get_stats()
    print("__CRAWLOPS_STATS__" + json.dumps(stats, default=serialize), flush=True)
    if errors:
        print("\n".join(errors), file=sys.stderr)
    sys.exit(1 if errors or stats.get("finish_reason") != "finished" else 0)


if __name__ == "__main__":
    main()
