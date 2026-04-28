import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

INDEED_BASE_URL = "https://ar.indeed.com/jobs"
INDEED_LOG_PATH = Path("logs/scraper_indeed.log")


def setup_indeed_logger() -> logging.Logger:
    """Configura logger dedicado para Indeed (archivo + consola)."""
    INDEED_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("indeed_scraper")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(INDEED_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def normalize_whitespace(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def build_indeed_search_url(keywords: str, location: str) -> str:
    return f"{INDEED_BASE_URL}?q={quote_plus(keywords)}&l={quote_plus(location)}"


def _safe_inner_text(item, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            loc = item.locator(selector).first
            if loc.count() > 0:
                text = normalize_whitespace(loc.inner_text(timeout=1000))
                if text:
                    return text
        except Exception:
            continue
    return ""


def _safe_href(item, selectors: List[str]) -> str:
    for selector in selectors:
        try:
            loc = item.locator(selector).first
            if loc.count() > 0:
                href = loc.get_attribute("href", timeout=1000)
                if href:
                    if href.startswith("/"):
                        return f"https://ar.indeed.com{href}"
                    return href
        except Exception:
            continue
    return ""


def _extract_card(card) -> Dict[str, str]:
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    title = _safe_inner_text(card, ["h2 a span", "h2 span", "[data-testid='jobTitle']"])
    link = _safe_href(card, ["h2 a", "a.jcs-JobTitle", "a[data-jk]"])

    return {
        "title": title,
        "company": _safe_inner_text(card, ["[data-testid='company-name']", ".companyName", "span[data-testid='company-name']"]),
        "location": _safe_inner_text(card, ["[data-testid='text-location']", ".companyLocation"]),
        "link": link,
        "postedDate": _safe_inner_text(card, ["[data-testid='myJobsStateDate']", ".date"]),
        "description": _safe_inner_text(card, ["[data-testid='job-snippet']", ".job-snippet"]),
        "source": "Indeed",
        "scraped_at": timestamp,
        "status": "encontrada",
        "score": "",
        "category": "",
        "action_required": "",
        "notes": "",
        "manual_required": "false",
        "manual_reason": "",
    }


def collect_indeed_offers(
    page,
    keywords: List[str],
    location: str,
    max_results: int,
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, str]]:
    """Recolecta ofertas de Indeed Argentina sin evadir captchas ni bloqueos."""
    logger = logger or setup_indeed_logger()
    logger.info("Inicio de scraping de Indeed Argentina")

    offers: List[Dict[str, str]] = []
    for keyword in keywords:
        if len(offers) >= max_results:
            break

        search_url = build_indeed_search_url(keyword, location)
        logger.info("Buscando en Indeed keyword='%s' location='%s' url=%s", keyword, location, search_url)

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            logger.warning("Timeout al cargar Indeed para keyword '%s'", keyword)
            continue
        except Exception as exc:
            logger.error("Error navegando Indeed para keyword '%s': %s", keyword, exc)
            continue

        try:
            block_marker = page.locator("text=/captcha|robot|access denied|forbidden|blocked/i").first
            if block_marker.is_visible(timeout=800):
                logger.warning(
                    "Indeed mostró bloqueo/captcha para keyword '%s'. Se omite sin evadir protección.",
                    keyword,
                )
                continue
        except Exception:
            pass

        cards = None
        for selector in ["[data-testid='slider_item']", "div.job_seen_beacon", "li:has(h2 a)"]:
            candidate = page.locator(selector)
            try:
                count = candidate.count()
            except Exception:
                count = 0
            if count > 0:
                cards = candidate
                logger.info("Indeed: %s resultados potenciales con selector '%s'", count, selector)
                break

        if cards is None:
            logger.info("Indeed sin resultados para keyword '%s'", keyword)
            continue

        try:
            total_cards = cards.count()
        except Exception:
            total_cards = 0

        if total_cards == 0:
            logger.info("Indeed sin resultados visibles para keyword '%s'", keyword)
            continue

        for idx in range(total_cards):
            if len(offers) >= max_results:
                break
            try:
                offer = _extract_card(cards.nth(idx))
                if offer["link"]:
                    offers.append(offer)
            except Exception as exc:
                logger.warning("Error extrayendo tarjeta idx=%s en keyword '%s': %s", idx, keyword, exc)

    logger.info("Indeed: %s ofertas recolectadas en total", len(offers))
    if not offers:
        logger.info("Indeed no devolvió resultados para la configuración actual")
    return offers
