from scraping.scrapers.agrofy_scraper import AgrofyScraper
from scraping.scrapers.mercadolibre_scraper import MercadoLibreScraper
from scraping.scrapers.syngenta_scraper import SyngentaScraper
from scraping.scrapers.bayer_scraper import BayerScraper
from scraping.scrapers.basf_scraper import BasfScraper
from scraping.scrapers.cofepris_scraper import CofeprisScraper
from scraping.scrapers.amazon_scraper import AmazonScraper

ALL_SCRAPERS = [
    AgrofyScraper,
    MercadoLibreScraper,
    SyngentaScraper,
    BayerScraper,
    BasfScraper,
    CofeprisScraper,
    AmazonScraper,
]

__all__ = [
    "AgrofyScraper",
    "MercadoLibreScraper",
    "SyngentaScraper",
    "BayerScraper",
    "BasfScraper",
    "CofeprisScraper",
    "AmazonScraper",
    "ALL_SCRAPERS",
]
