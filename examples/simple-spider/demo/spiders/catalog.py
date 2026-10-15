import asyncio
from pathlib import Path
import scrapy


class CatalogSpider(scrapy.Spider):
    name = "catalog"

    def __init__(self, url=None, prefix="demo", delay="0", **kwargs):
        super().__init__(**kwargs)
        # Local fixture is deterministic and works without internet or DNS.
        self.start_urls = [url or (Path(__file__).parents[1] / "fixture.html").as_uri()]
        self.prefix = prefix
        self.delay = max(0, min(float(delay), 30))

    async def parse(self, response):
        for product in response.css("article"):
            await asyncio.sleep(self.delay)
            yield {
                "name": self.prefix + "-" + product.css("h2::text").get(),
                "price": product.css(".price::text").get(),
            }
