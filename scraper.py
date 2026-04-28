import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import config
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from storage import load_offers, save_offers, upsert_offer

BASE_URL = "https://www.bumeran.com.ar"
LOG_PATH = Path("logs/scraper.log")
UNAVAILABLE = "no disponible"


def setup_logging() -> logging.Logger:
    """Configura logger a archivo y consola."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("bumeran_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def normalize_whitespace(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def build_search_url(keyword: str, location: str) -> str:
    encoded_keyword = quote_plus(keyword)
    encoded_location = quote_plus(location)
    return f"{BASE_URL}/empleos-busqueda.html?palabra={encoded_keyword}&ubicacion={encoded_location}"


def safe_text(item, selectors: List[str], logger: logging.Logger, field_name: str) -> str:
    """Extrae texto de forma tolerante a errores y retorna fallback si falla."""
    for selector in selectors:
        try:
            loc = item.locator(selector).first
            if loc.count() > 0:
                text = normalize_whitespace(loc.inner_text(timeout=1500))
                if text:
                    return text
        except Exception as exc:
            logger.warning("Error extrayendo campo '%s' con selector '%s': %s", field_name, selector, exc)

    logger.warning("Campo '%s' no disponible en la oferta actual", field_name)
    return UNAVAILABLE


def safe_href(item, selectors: List[str], logger: logging.Logger) -> str:
    """Extrae link de forma segura. Si falla, retorna fallback."""
    for selector in selectors:
        try:
            loc = item.locator(selector).first
            if loc.count() > 0:
                href = loc.get_attribute("href", timeout=1500)
                if href:
                    if href.startswith("/"):
                        return f"{BASE_URL}{href}"
                    return href
        except Exception as exc:
            logger.warning("Error extrayendo link con selector '%s': %s", selector, exc)

    logger.warning("Campo 'link' no disponible en la oferta actual")
    return UNAVAILABLE


def extract_offer(item, logger: logging.Logger) -> Dict[str, str]:
    """Mapea una oferta de Bumeran al esquema central de almacenamiento."""
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "title": safe_text(item, ["h2", "h3", "a[data-test='job-title']", "[class*='title']"], logger, "title"),
        "company": safe_text(item, ["[data-test='company-name']", "[class*='company']", "span"], logger, "company"),
        "location": safe_text(item, ["[data-test='job-location']", "[class*='location']"], logger, "location"),
        "link": safe_href(item, ["a[data-test='job-title']", "h2 a", "h3 a", "a"], logger),
        "source": "Bumeran",
        "scraped_at": timestamp,
        "status": "new",
        "score": "",
        "category": "",
        "action_required": "",
        "notes": "",
        "manual_required": "false",
        "manual_reason": "",
    }


def collect_for_keyword(page, keyword: str, location: str, logger: logging.Logger) -> List[Dict[str, str]]:
    """Recolecta ofertas para una keyword hasta el límite de configuración."""
    offers: List[Dict[str, str]] = []
    search_url = build_search_url(keyword, location)
    logger.info("Buscando keyword '%s' en URL: %s", keyword, search_url)

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except PlaywrightTimeoutError:
        logger.error("Timeout cargando la búsqueda para keyword '%s'", keyword)
        return offers
    except Exception as exc:
        logger.error("Error navegando búsqueda para keyword '%s': %s", keyword, exc)
        return offers

    card_selectors = [
        "article",
        "[data-test='job-card']",
        "[class*='job']",
        "[class*='offer']",
    ]

    cards = None
    for selector in card_selectors:
        candidate = page.locator(selector)
        try:
            count = candidate.count()
        except Exception:
            count = 0

        if count > 0:
            cards = candidate
            logger.info("Se encontraron %s nodos potenciales con selector '%s'", count, selector)
            break

    if cards is None:
        logger.error("No se encontraron contenedores de ofertas para keyword '%s'", keyword)
        return offers

    try:
        total_cards = cards.count()
    except Exception:
        total_cards = 0

    if total_cards == 0:
        logger.error("La lista de ofertas está vacía para keyword '%s'", keyword)
        return offers

    for idx in range(total_cards):
        if len(offers) >= config.max_results:
            break

        try:
            item = cards.nth(idx)
            offer = extract_offer(item, logger)
            if offer["link"] != UNAVAILABLE:
                offers.append(offer)
            else:
                logger.info("Oferta omitida por falta de link (idx=%s, keyword='%s')", idx, keyword)
        except Exception as exc:
            logger.error("Error procesando oferta idx=%s keyword='%s': %s", idx, keyword, exc)

    logger.info("Keyword '%s': %s ofertas recolectadas", keyword, len(offers))
    return offers


def main() -> None:
    logger = setup_logging()
    logger.info("Inicio de scraping de ofertas públicas de Bumeran")

    offers_db = load_offers()
    logger.info("Base central cargada: %s ofertas", len(offers_db))

    scraped_offers: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            for keyword in config.keywords:
                if len(scraped_offers) >= config.max_results:
                    break

                offers = collect_for_keyword(page, keyword, config.location, logger)
                scraped_offers.extend(offers)
                if len(scraped_offers) > config.max_results:
                    scraped_offers = scraped_offers[: config.max_results]
        except Exception as exc:
            logger.exception("Error general durante el scraping: %s", exc)
        finally:
            if browser:
                browser.close()

    inserted = 0
    skipped_existing = 0
    for offer in scraped_offers:
        if upsert_offer(offers_db, offer):
            inserted += 1
        else:
            skipped_existing += 1

    save_offers(offers_db)

    logger.info("Nuevas ofertas agregadas: %s", inserted)
    logger.info("Ofertas ya existentes (sin duplicar): %s", skipped_existing)
    logger.info("Total base central: %s", len(offers_db))
    logger.info("Proceso finalizado")


if __name__ == "__main__":
    main()
