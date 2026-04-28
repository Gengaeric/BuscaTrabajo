import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urlencode

import config
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from scrapers.indeed_scraper import collect_indeed_offers, setup_indeed_logger
from storage import load_offers, save_offers, upsert_offer

BASE_URL = "https://www.bumeran.com.ar"
LOG_PATH = Path("logs/scraper.log")
NO_RESULTS_SCREENSHOT_PATH = Path("logs/bumeran_no_results.png")
DEBUG_HTML_PATH = Path("logs/bumeran_debug.html")
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
    query = urlencode(
        {
            "palabra": keyword,
            # Bumeran usa location en la búsqueda web actual.
            "location": location,
        },
        quote_via=quote_plus,
    )
    return f"{BASE_URL}/empleos-busqueda.html?{query}"


def build_search_url_fallbacks(keyword: str, location: str) -> List[str]:
    """Devuelve variantes por si Bumeran cambia parámetros de búsqueda."""
    encoded_keyword = quote_plus(keyword)
    encoded_location = quote_plus(location)
    return [
        build_search_url(keyword, location),
        f"{BASE_URL}/empleos-busqueda.html?palabra={encoded_keyword}&ubicacion={encoded_location}",
        f"{BASE_URL}/empleos.html?palabra={encoded_keyword}&location={encoded_location}",
    ]


def classify_debug_state_from_html(html: str) -> str:
    content = html.lower()
    checks = {
        "captcha": [
            "captcha",
            "recaptcha",
            "hcaptcha",
            "no soy un robot",
            "i am human",
            "are you human",
            "security challenge",
        ],
        "bloqueo_anti_bot": [
            "access denied",
            "forbidden",
            "request blocked",
            "bot detection",
            "cloudflare",
            "akamai",
        ],
        "error_pagina": [
            "500",
            "502",
            "503",
            "504",
            "service unavailable",
            "something went wrong",
            "ocurrió un error",
            "página no encontrada",
        ],
        "sin_resultados": [
            "no hay ofertas",
            "no encontramos",
            "sin resultados",
            "no hay resultados",
        ],
    }
    for label, patterns in checks.items():
        if any(pattern in content for pattern in patterns):
            return label
    if "__next" in content and "application/json" in content and "script" in content:
        return "estructura_js_o_selectores_desactualizados"
    return "desconocido"


def analyze_debug_artifacts(logger: logging.Logger) -> str:
    """Analiza el HTML de debug ya guardado para detectar causa probable."""
    if not DEBUG_HTML_PATH.exists():
        logger.warning("No existe HTML de debug para analizar: %s", DEBUG_HTML_PATH)
        return "sin_html_debug"

    html = DEBUG_HTML_PATH.read_text(encoding="utf-8", errors="ignore")
    diagnosis = classify_debug_state_from_html(html)
    logger.info("Diagnóstico automático de Bumeran (desde debug HTML): %s", diagnosis)
    return diagnosis


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


def persist_debug_artifacts(page, logger: logging.Logger, keyword: str) -> None:
    """Guarda screenshot + HTML cuando no se encuentran ofertas."""
    NO_RESULTS_SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        page.screenshot(path=str(NO_RESULTS_SCREENSHOT_PATH), full_page=True)
        logger.info(
            "Screenshot de debug guardado para keyword '%s': %s",
            keyword,
            NO_RESULTS_SCREENSHOT_PATH,
        )
    except Exception as exc:
        logger.error("No se pudo guardar screenshot de debug para '%s': %s", keyword, exc)

    try:
        html = page.content()
        DEBUG_HTML_PATH.write_text(html, encoding="utf-8")
        logger.info("HTML de debug guardado para keyword '%s': %s", keyword, DEBUG_HTML_PATH)
    except Exception as exc:
        logger.error("No se pudo guardar HTML de debug para '%s': %s", keyword, exc)


def extract_offer(item, logger: logging.Logger) -> Dict[str, str]:
    """Mapea una oferta de Bumeran al esquema central de almacenamiento."""
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return {
        "title": safe_text(
            item,
            [
                "[data-qa='job-title']",
                "[data-testid='job-title']",
                "a[data-test='job-title']",
                "h2 a",
                "h3 a",
                "h2",
                "h3",
                "a[href*='/empleos/']",
                "[class*='title']",
                "[class*='puesto']",
            ],
            logger,
            "title",
        ),
        "company": safe_text(
            item,
            [
                "[data-qa='job-company']",
                "[data-qa='company-name']",
                "[data-testid='job-company']",
                "[data-test='company-name']",
                "[class*='company']",
                "[class*='empresa']",
            ],
            logger,
            "company",
        ),
        "location": safe_text(
            item,
            [
                "[data-qa='job-location']",
                "[data-qa='job-city']",
                "[data-testid='job-location']",
                "[data-test='job-location']",
                "[class*='location']",
                "[class*='ubicacion']",
                "[class*='city']",
            ],
            logger,
            "location",
        ),
        "link": safe_href(
            item,
            [
                "a[data-qa='job-title']",
                "a[data-testid='job-title']",
                "a[data-test='job-title']",
                "h2 a",
                "h3 a",
                "a[href*='/empleos/']",
                "a[href*='.html']",
                "a",
            ],
            logger,
        ),
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


def collect_for_keyword(page, keyword: str, location: str, logger: logging.Logger) -> tuple[List[Dict[str, str]], bool]:
    """Recolecta ofertas para una keyword hasta el límite de configuración."""
    offers: List[Dict[str, str]] = []
    requires_manual_review = False
    search_urls = build_search_url_fallbacks(keyword, location)
    logger.info("Buscando keyword '%s' (URLs candidatas: %s)", keyword, " | ".join(search_urls))

    last_navigation_error = None
    for search_url in search_urls:
        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(1200)
            logger.info("Búsqueda cargada para keyword '%s' con URL: %s", keyword, search_url)
            break
        except PlaywrightTimeoutError as exc:
            last_navigation_error = exc
            logger.warning("Timeout con URL '%s' para keyword '%s'. Probaré variante.", search_url, keyword)
        except Exception as exc:
            last_navigation_error = exc
            logger.warning("Error de navegación con URL '%s': %s", search_url, exc)
    else:
        logger.error("No se pudo navegar ninguna URL para keyword '%s': %s", keyword, last_navigation_error)
        return offers, requires_manual_review

    card_selectors = [
        "[data-qa='job-card']",
        "[data-qa='aviso-item']",
        "[data-testid='job-card']",
        "[data-testid='job-item']",
        "[data-test='job-card']",
        "[data-qa='search-results-list'] article",
        "article[data-qa*='job']",
        "article[data-testid*='job']",
        "article:has(a[href*='/empleos/'])",
        "li:has(a[href*='/empleos/'])",
        "div:has(a[href*='/empleos/'])",
    ]

    no_results_or_error_selectors = [
        "text=/captcha|robot|verificación|access denied|forbidden|bloqueado/i",
        "text=/no encontramos|sin resultados|no hay resultados/i",
        "text=/ocurrió un error|algo salió mal|service unavailable/i",
    ]
    for marker in no_results_or_error_selectors:
        try:
            if page.locator(marker).first.is_visible(timeout=1200):
                logger.warning("Se detectó marcador de error/bloqueo/no-resultados: %s", marker)
                persist_debug_artifacts(page, logger, keyword)
                diagnosis = analyze_debug_artifacts(logger)
                if diagnosis in {"captcha", "bloqueo_anti_bot"}:
                    requires_manual_review = True
                    logger.error(
                        "Bumeran bloquea o desafía automatización para keyword '%s' (diagnóstico=%s). "
                        "Requiere revisión manual.",
                        keyword,
                        diagnosis,
                    )
                return offers, requires_manual_review
        except Exception:
            pass

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
        persist_debug_artifacts(page, logger, keyword)
        diagnosis = analyze_debug_artifacts(logger)
        if diagnosis in {"captcha", "bloqueo_anti_bot"}:
            requires_manual_review = True
            logger.error(
                "Bumeran bloquea Playwright para keyword '%s' (diagnóstico=%s). Requiere revisión manual.",
                keyword,
                diagnosis,
            )
        return offers, requires_manual_review

    try:
        total_cards = cards.count()
    except Exception:
        total_cards = 0

    if total_cards == 0:
        logger.error("La lista de ofertas está vacía para keyword '%s'", keyword)
        persist_debug_artifacts(page, logger, keyword)
        analyze_debug_artifacts(logger)
        return offers, requires_manual_review

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
    if not offers:
        logger.warning("No se extrajeron ofertas válidas para keyword '%s'", keyword)
        persist_debug_artifacts(page, logger, keyword)
        analyze_debug_artifacts(logger)
    return offers, requires_manual_review


def main() -> None:
    logger = setup_logging()
    indeed_logger = setup_indeed_logger()
    logger.info("Inicio de scraping de ofertas públicas de Bumeran")
    logger.info(
        "Configuración compartida entre fuentes: keywords=%s | location=%s | max_results=%s | output=%s",
        config.keywords,
        config.location,
        config.max_results,
        config.output_file,
    )

    offers_db = load_offers()
    logger.info("Base central cargada: %s ofertas", len(offers_db))

    scraped_offers: List[Dict[str, str]] = []
    bumeran_requires_manual_review = False
    bumeran_had_error = False

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            try:
                for keyword in config.keywords:
                    if len(scraped_offers) >= config.max_results:
                        break

                    offers, blocked = collect_for_keyword(page, keyword, config.location, logger)
                    if blocked:
                        bumeran_requires_manual_review = True
                    scraped_offers.extend(offers)
                    if len(scraped_offers) > config.max_results:
                        scraped_offers = scraped_offers[: config.max_results]
            except Exception as exc:
                bumeran_had_error = True
                logger.exception("Error durante flujo de Bumeran: %s", exc)

            if bumeran_requires_manual_review:
                logger.warning(
                    "Bumeran requiere revisión manual por bloqueo anti-automatización. "
                    "Se ejecuta Indeed Argentina de todos modos."
                )
            if bumeran_had_error:
                logger.warning(
                    "Bumeran falló durante la ejecución. Se ejecuta Indeed Argentina de todos modos."
                )

            logger.info("Inicio de flujo de Indeed Argentina (post-Bumeran)")
            indeed_offers = collect_indeed_offers(
                page=page,
                keywords=config.keywords,
                location=config.location,
                max_results=max(0, config.max_results - len(scraped_offers)),
                logger=indeed_logger,
            )
            scraped_offers.extend(indeed_offers)
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
