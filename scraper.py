import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.bumeran.com.ar"
KEYWORDS = ["Recursos Humanos", "HR"]
LOCATION = "Buenos Aires"
MAX_RESULTS = 25
CSV_PATH = Path("data/offers_bumeran.csv")
LOG_PATH = Path("logs/scraper.log")


def setup_logging() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    logger = logging.getLogger("bumeran_scraper")
    logger.addHandler(logging.StreamHandler())
    return logger


def normalize_whitespace(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def build_search_url(keyword: str, location: str) -> str:
    encoded_keyword = quote_plus(keyword)
    encoded_location = quote_plus(location)
    # URL semántica de búsqueda con filtros pre-cargados
    return f"{BASE_URL}/empleos-busqueda.html?palabra={encoded_keyword}&ubicacion={encoded_location}"


def safe_text(item, selectors: List[str], logger: logging.Logger) -> str:
    for selector in selectors:
        try:
            loc = item.locator(selector).first
            if loc.count() > 0:
                text = normalize_whitespace(loc.inner_text(timeout=1500))
                if text:
                    return text
        except Exception as exc:
            logger.debug("No se pudo obtener texto con selector %s: %s", selector, exc)
    return ""


def safe_href(item, selectors: List[str], logger: logging.Logger) -> str:
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
            logger.debug("No se pudo obtener href con selector %s: %s", selector, exc)
    return ""


def extract_offer(item, logger: logging.Logger) -> Dict[str, str]:
    return {
        "titulo": safe_text(item, ["h2", "h3", "a[data-test='job-title']", "[class*='title']"], logger),
        "empresa": safe_text(item, ["[data-test='company-name']", "[class*='company']", "span"], logger),
        "ubicacion": safe_text(item, ["[data-test='job-location']", "[class*='location']"], logger),
        "link": safe_href(item, ["a[data-test='job-title']", "h2 a", "h3 a", "a"], logger),
        "fecha_publicacion": safe_text(
            item,
            ["time", "[data-test='job-date']", "[class*='date']", "[class*='published']"],
            logger,
        ),
    }


def collect_for_keyword(page, keyword: str, logger: logging.Logger) -> List[Dict[str, str]]:
    offers: List[Dict[str, str]] = []
    search_url = build_search_url(keyword, LOCATION)
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
        if len(offers) >= MAX_RESULTS:
            break

        try:
            item = cards.nth(idx)
            offer = extract_offer(item, logger)
            if offer["titulo"] and offer["link"]:
                offer["keyword_busqueda"] = keyword
                offers.append(offer)
            else:
                logger.info("Oferta omitida por datos insuficientes (idx=%s, keyword='%s')", idx, keyword)
        except Exception as exc:
            logger.error("Error procesando oferta idx=%s keyword='%s': %s", idx, keyword, exc)
            continue

    logger.info("Keyword '%s': %s ofertas válidas recolectadas", keyword, len(offers))
    return offers


def write_csv(rows: List[Dict[str, str]], logger: logging.Logger) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = ["titulo", "empresa", "ubicacion", "link", "fecha_publicacion", "keyword_busqueda"]

    try:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        logger.info("CSV generado en %s con %s filas", CSV_PATH, len(rows))
    except Exception as exc:
        logger.error("No se pudo escribir el CSV %s: %s", CSV_PATH, exc)


def deduplicate(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    unique_rows = []

    for row in rows:
        key = row.get("link") or f"{row.get('titulo','')}-{row.get('empresa','')}"
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    return unique_rows


def main() -> None:
    logger = setup_logging()
    logger.info("Inicio de scraping de ofertas públicas de Bumeran")

    all_offers: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            for keyword in KEYWORDS:
                if len(all_offers) >= MAX_RESULTS:
                    break

                offers = collect_for_keyword(page, keyword, logger)
                all_offers.extend(offers)
                if len(all_offers) > MAX_RESULTS:
                    all_offers = all_offers[:MAX_RESULTS]
        except Exception as exc:
            logger.exception("Error general durante el scraping: %s", exc)
        finally:
            if browser:
                browser.close()

    deduped = deduplicate(all_offers)[:MAX_RESULTS]

    if not deduped:
        logger.error("No se obtuvieron ofertas válidas. Se genera CSV vacío con cabeceras.")

    write_csv(deduped, logger)
    logger.info("Proceso finalizado")


if __name__ == "__main__":
    main()
