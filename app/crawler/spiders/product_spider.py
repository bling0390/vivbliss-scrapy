import hashlib
import re
from typing import Iterable, List

import scrapy
from scrapy import Request

from app.crawler.items import ProductItem, ProductMedia


class ProductSpider(scrapy.Spider):
    name = "products"
    allowed_domains: List[str] = ["vivbliss.com"]
    start_urls = ["https://vivbliss.com/products/"]

    def parse(self, response):
        yield from self.parse_category(response)

    def parse_category(self, response):
        links = set()
        links.update(
            response.css(
                "div#minimog-main-post div.grid-item.product a.woocommerce-LoopProduct-link.woocommerce-loop-product__link::attr(href)"
            ).getall()
        )
        links.update(
            response.css(
                "div#minimog-main-post div.grid-item.product h3.woocommerce-loop-product__title a::attr(href)"
            ).getall()
        )

        for href in sorted(links):
            if "/product/" not in href:
                continue
            yield response.follow(href, callback=self.parse_detail)

        next_page = response.css(
            "nav.woocommerce-pagination[data-type='load-more'] button.shop-load-more-button::attr(data-url)"
        ).get()
        if next_page:
            yield response.follow(next_page, callback=self.parse_category)

    def parse_detail(self, response):
        product_key = self._extract_product_key(response)
        title = response.css("h1.product_title.entry-title span::text").get()
        price, currency = self._extract_price(response)
        images = self._extract_images(response)
        videos = self._extract_videos(response)

        media_items: List[ProductMedia] = []
        for img in images:
            media = ProductMedia()
            media["media_type"] = "image"
            media["source_url"] = img
            media["local_path"] = None
            media_items.append(media)
        for vid in videos:
            media = ProductMedia()
            media["media_type"] = "video"
            media["source_url"] = vid
            media["local_path"] = None
            media_items.append(media)

        item = ProductItem()
        item["product_key"] = product_key
        item["url"] = response.url
        item["title"] = title
        item["price"] = {"amount": price, "currency": currency} if price else None
        item["media"] = media_items
        item["raw"] = {"path": response.url}
        yield item

    def _extract_product_key(self, response) -> str:
        pid = response.css("div[id^='product-']::attr(id)").get()
        if pid:
            match = re.search(r"product-(\d+)", pid)
            if match:
                return match.group(1)

        cls = " ".join(response.css("div.entry-product.product::attr(class)").getall())
        match = re.search(r"post-(\d+)", cls)
        if match:
            return match.group(1)

        return hashlib.sha1(response.url.encode("utf-8")).hexdigest()

    def _extract_price(self, response):
        price_block = response.css("div.entry-price-wrap div.price")

        def clean_amount(sel):
            text = " ".join(sel.css("::text").getall()).strip()
            m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", text)
            return m.group(1) if m else None

        currency = price_block.css(".woocommerce-Price-currencySymbol::text").get()
        amount = clean_amount(price_block.css("ins")) or clean_amount(price_block)
        return amount, currency

    def _extract_images(self, response) -> List[str]:
        images: List[str] = []
        for slide in response.css("div.gallery-main-slides-o-html .swiper-slide"):
            url = slide.attrib.get("data-src") or slide.css("img::attr(src)").get()
            if url:
                images.append(response.urljoin(url))
        return sorted(set(images))

    def _extract_videos(self, response) -> List[str]:
        videos: List[str] = []
        videos.extend(
            response.urljoin(url)
            for url in response.css("div[id^='product-video-'] video::attr(src)").getall()
            if url
        )
        if not videos:
            found = re.findall(r"""["'](https?://[^\s"'<>]+?\.(?:mp4|m3u8))["']""", response.text)
            videos.extend(response.urljoin(url) for url in found)
        return sorted(set(videos))
