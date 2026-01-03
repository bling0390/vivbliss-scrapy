import os
from pathlib import Path

BOT_NAME = "vivbliss"

SPIDER_MODULES = ["app.crawler.spiders"]
NEWSPIDER_MODULE = "app.crawler.spiders"

ROBOTSTXT_OBEY = False
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "0"))
CONCURRENT_REQUESTS = int(os.getenv("CONCURRENT_REQUESTS", "8"))

ITEM_PIPELINES = {
    "app.crawler.pipelines.MongoPipeline": 300,
}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_STDOUT = True

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
JOBDIR = os.getenv("SCRAPY_JOBDIR", str(DATA_DIR / "state" / "scrapy-job"))

FEEDS = {}
