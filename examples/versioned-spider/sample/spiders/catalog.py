import json
from pathlib import Path

import scrapy

VERSION = "v1"


class CatalogSpider(scrapy.Spider):
    name = "catalog"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_urls = [(Path(__file__).parents[1] / "fixture.html").as_uri()]

    def parse(self, response):
        items = [
            {"name": name, "version": VERSION}
            for name in response.css("article::text").getall()
        ]
        if VERSION == "v2":
            items.append({"name": "Eraser", "version": VERSION})
        output = Path("/tmp/.output/items.jsonl")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(item) + "\n" for item in items))
        saved = [json.loads(line) for line in output.read_text().splitlines()]
        assert saved == items
        self.logger.info("SAMPLE_RESULT %s", json.dumps({"version": VERSION, "items": saved}))
        yield from items
