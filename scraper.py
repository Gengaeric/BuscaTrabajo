import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus

import config
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.bumeran.com.ar"
CSV_PATH = Path(config.output_file)
LOG_PATH = Path("logs/scraper.log")
UNAVAILABLE = "no disponible"
CSV_COLUMNS = [
    "titulo",
    "empresa",
    "ubicacion",
    "link",
    "fecha_publicacion",
    "keyword_busqueda",
    "source",
    "scraped_at",
    "status",
]


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


def extract_offer(item, keyword: str, logger: logging.Logger) -> Dict[str, str]:
    """Mapea una oferta de Bumeran al esquema común de salida."""
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "titulo": safe_text(item, ["h2", "h3", "a[data-test='job-title']", "[class*='title']"], logger, "titulo"),
        "empresa": safe_text(item, ["[data-test='company-name']", "[class*='company']", "span"], logger, "empresa"),
        "ubicacion": safe_text(item, ["[data-test='job-location']", "[class*='location']"], logger, "ubicacion"),
        "link": safe_href(item, ["a[data-test='job-title']", "h2 a", "h3 a", "a"], logger),
        "fecha_publicacion": safe_text(
            item,
            ["time", "[data-test='job-date']", "[class*='date']", "[class*='published']"],
            logger,
            "fecha_publicacion",
        ),
        "keyword_busqueda": keyword,
        "source": "Bumeran",
        "scraped_at": timestamp,
        "status": "encontrada",
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
            offer = extract_offer(item, keyword, logger)
            if offer["link"] != UNAVAILABLE:
                offers.append(offer)
            else:
                logger.info("Oferta omitida por falta de link (idx=%s, keyword='%s')", idx, keyword)
        except Exception as exc:
            logger.error("Error procesando oferta idx=%s keyword='%s': %s", idx, keyword, exc)

    logger.info("Keyword '%s': %s ofertas recolectadas", keyword, len(offers))
    return offers


def read_existing_rows_and_links(logger: logging.Logger) -> tuple[List[Dict[str, str]], Set[str]]:
    """Carga CSV previo para evitar guardar links duplicados."""
    if not CSV_PATH.exists():
        return [], set()

    existing_rows: List[Dict[str, str]] = []
    existing_links: Set[str] = set()

    try:
        with CSV_PATH.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                normalized = {column: row.get(column, UNAVAILABLE) or UNAVAILABLE for column in CSV_COLUMNS}
                existing_rows.append(normalized)
                link = normalized.get("link", "")
                if link and link != UNAVAILABLE:
                    existing_links.add(link)

        logger.info("CSV previo detectado: %s filas, %s links únicos", len(existing_rows), len(existing_links))
    except Exception as exc:
        logger.error("No se pudo leer el CSV previo %s: %s", CSV_PATH, exc)

    return existing_rows, existing_links


def deduplicate_new_rows(new_rows: List[Dict[str, str]], existing_links: Set[str], logger: logging.Logger) -> List[Dict[str, str]]:
    """Elimina duplicados de nuevas filas por link (contra CSV y lote actual)."""
    deduped: List[Dict[str, str]] = []
    seen_links = set(existing_links)

    for row in new_rows:
        link = row.get("link", UNAVAILABLE)
        if link == UNAVAILABLE:
            logger.info("Oferta omitida por link no disponible")
            continue
        if link in seen_links:
            logger.info("Oferta duplicada omitida: %s", link)
            continue

        seen_links.add(link)
        deduped.append(row)

    return deduped


def write_csv(rows: List[Dict[str, str]], logger: logging.Logger) -> None:
    """Escribe todas las filas finales al CSV de salida."""
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        logger.info("CSV generado en %s con %s filas", CSV_PATH, len(rows))
    except Exception as exc:
        logger.error("No se pudo escribir el CSV %s: %s", CSV_PATH, exc)


def main() -> None:
    logger = setup_logging()
    logger.info("Inicio de scraping de ofertas públicas de Bumeran")

    existing_rows, existing_links = read_existing_rows_and_links(logger)
    new_offers: List[Dict[str, str]] = []

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            for keyword in config.keywords:
                if len(new_offers) >= config.max_results:
                    break

                offers = collect_for_keyword(page, keyword, config.location, logger)
                new_offers.extend(offers)
                if len(new_offers) > config.max_results:
                    new_offers = new_offers[: config.max_results]
        except Exception as exc:
            logger.exception("Error general durante el scraping: %s", exc)
        finally:
            if browser:
                browser.close()

    unique_new = deduplicate_new_rows(new_offers, existing_links, logger)

    if not unique_new:
        logger.warning("No se encontraron nuevas ofertas para agregar al CSV")

    final_rows = existing_rows + unique_new
    write_csv(final_rows, logger)
    logger.info("Proceso finalizado")


if __name__ == "__main__":
    main()
