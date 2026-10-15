from pathlib import Path
from babel.numbers import parse_decimal
import scrapy


class PricesSpider(scrapy.Spider):
    name = "prices"

    def __init__(self, locale="en_US", **kwargs):
        super().__init__(**kwargs)
        self.locale = locale
        self.start_urls = [(Path(__file__).parents[1] / "fixture.html").as_uri()]

    def parse(self, response):
        for product in response.css("article"):
            yield {
                "name": product.css("h2::text").get(),
                "price": str(parse_decimal(product.css(".price::text").get(), locale=self.locale)),
            }
