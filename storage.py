import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

UNAVAILABLE = "no disponible"

OFFERS_COLUMNS = [
    "id",
    "title",
    "company",
    "location",
    "link",
    "source",
    "scraped_at",
    "status",
    "score",
    "category",
    "action_required",
    "notes",
    "manual_required",
    "manual_reason",
]

TRACKING_FIELDS = ["status", "score", "category", "action_required", "notes", "manual_required", "manual_reason"]

LEGACY_TO_NORMALIZED = {
    "titulo": "title",
    "empresa": "company",
    "ubicacion": "location",
}

DEFAULT_VALUES = {
    "id": "",
    "title": UNAVAILABLE,
    "company": UNAVAILABLE,
    "location": UNAVAILABLE,
    "link": UNAVAILABLE,
    "source": "Bumeran",
    "scraped_at": "",
    "status": "encontrada",
    "score": "",
    "category": "",
    "action_required": "",
    "notes": "",
    "manual_required": "false",
    "manual_reason": "",
}


def _normalize_value(value: Optional[str], fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _build_offer_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def _normalize_offer(raw_offer: Dict[str, str]) -> Dict[str, str]:
    normalized = dict(DEFAULT_VALUES)

    for key, value in raw_offer.items():
        mapped_key = LEGACY_TO_NORMALIZED.get(key, key)
        if mapped_key in normalized:
            normalized[mapped_key] = _normalize_value(value, normalized[mapped_key])

    if normalized["link"] != UNAVAILABLE:
        normalized["id"] = _build_offer_id(normalized["link"])

    if normalized["id"] and raw_offer:
        for field in TRACKING_FIELDS:
            if field in raw_offer:
                normalized[field] = _normalize_value(raw_offer.get(field), normalized[field])

    return normalized


def load_offers(csv_path: Path) -> List[Dict[str, str]]:
    if not csv_path.exists():
        return []

    offers: List[Dict[str, str]] = []

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            normalized = _normalize_offer(row)
            if not normalized["id"]:
                continue
            offers.append(normalized)

    return offers


def save_offers(csv_path: Path, offers: List[Dict[str, str]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_offers: List[Dict[str, str]] = []
    for offer in offers:
        normalized = _normalize_offer(offer)
        if normalized["id"]:
            normalized_offers.append(normalized)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OFFERS_COLUMNS)
        writer.writeheader()
        writer.writerows(normalized_offers)


def upsert_offer(existing_offers: List[Dict[str, str]], offer: Dict[str, str]) -> bool:
    normalized = _normalize_offer(offer)
    offer_id = normalized["id"]

    if not offer_id:
        return False

    for index, current in enumerate(existing_offers):
        if current.get("id") == offer_id:
            merged = dict(normalized)
            for field in TRACKING_FIELDS:
                merged[field] = current.get(field, DEFAULT_VALUES[field]) or DEFAULT_VALUES[field]
            existing_offers[index] = merged
            return False

    existing_offers.append(normalized)
    return True


def update_offer_status(existing_offers: List[Dict[str, str]], offer_id: str, status: str, notes: Optional[str] = None) -> bool:
    normalized_status = _normalize_value(status, DEFAULT_VALUES["status"])

    for offer in existing_offers:
        if offer.get("id") == offer_id:
            offer["status"] = normalized_status
            if notes is not None:
                offer["notes"] = notes.strip()
            return True

    return False
