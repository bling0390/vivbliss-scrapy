import scrapy


class ProductMedia(scrapy.Item):
    media_type = scrapy.Field()
    source_url = scrapy.Field()
    local_path = scrapy.Field()


class ProductItem(scrapy.Item):
    product_key = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    media = scrapy.Field()  # list[ProductMedia]
    raw = scrapy.Field()
