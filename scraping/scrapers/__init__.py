from scraping.scrapers.agrofy_scraper import AgrofyScraper
from scraping.scrapers.mercadolibre_scraper import MercadoLibreScraper
from scraping.scrapers.syngenta_scraper import SyngentaScraper
from scraping.scrapers.bayer_scraper import BayerScraper
from scraping.scrapers.basf_scraper import BasfScraper

ALL_SCRAPERS = [
    AgrofyScraper,
    MercadoLibreScraper,
    SyngentaScraper,
    BayerScraper,
    BasfScraper,
]

__all__ = [
    "AgrofyScraper",
    "MercadoLibreScraper",
    "SyngentaScraper",
    "BayerScraper",
    "BasfScraper",
    "ALL_SCRAPERS",
]
