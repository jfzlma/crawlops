BOT_NAME = "versioned_sample"
SPIDER_MODULES = ["sample.spiders"]
ROBOTSTXT_OBEY = False
LOG_LEVEL = "INFO"
# CrawlOps supplies logs, stats, and cancellation; the optional HTTP control
# server tries to write job metadata outside the writable /tmp directory.
EXTENSIONS = {"scrapy.extensions.remote_control.RemoteControl": None}
