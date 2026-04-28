import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import config

CSV_PATH = Path(config.output_file)

OFFER_FIELDS = [
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

TRACKING_FIELDS = [
    "status",
    "score",
    "category",
    "action_required",
    "notes",
    "manual_required",
    "manual_reason",
]

DEFAULTS = {
    "id": "",
    "title": "",
    "company": "",
    "location": "",
    "link": "",
    "source": "",
    "scraped_at": "",
    "status": "new",
    "score": "",
    "category": "",
    "action_required": "",
    "notes": "",
    "manual_required": "false",
    "manual_reason": "",
}


def _offer_id_from_link(link: str) -> str:
    normalized_link = (link or "").strip().lower()
    return hashlib.sha256(normalized_link.encode("utf-8")).hexdigest()


def normalize_offer(raw_offer: Optional[Dict[str, str]]) -> Dict[str, str]:
    raw_offer = raw_offer or {}
    offer = {field: str(raw_offer.get(field, DEFAULTS[field]) or DEFAULTS[field]) for field in OFFER_FIELDS}

    if offer["link"]:
        offer["id"] = _offer_id_from_link(offer["link"])
    elif not offer["id"]:
        offer["id"] = ""

    if offer["manual_required"].strip().lower() in {"true", "1", "yes", "si", "sí"}:
        offer["manual_required"] = "true"
    else:
        offer["manual_required"] = "false"

    return offer


def load_offers() -> List[Dict[str, str]]:
    if not CSV_PATH.exists():
        return []

    offers: List[Dict[str, str]] = []
    with CSV_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            normalized = normalize_offer(row)
            if normalized["id"]:
                offers.append(normalized)

    deduped: Dict[str, Dict[str, str]] = {}
    for offer in offers:
        deduped[offer["id"]] = offer

    return list(deduped.values())


def save_offers(offers: List[Dict[str, str]]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized_offers = []
    for offer in offers:
        normalized = normalize_offer(offer)
        if normalized["id"]:
            normalized_offers.append(normalized)

    deduped: Dict[str, Dict[str, str]] = {}
    for offer in normalized_offers:
        deduped[offer["id"]] = offer

    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OFFER_FIELDS)
        writer.writeheader()
        writer.writerows(deduped.values())


def upsert_offer(offers: List[Dict[str, str]], new_offer: Dict[str, str]) -> bool:
    normalized_new = normalize_offer(new_offer)
    offer_id = normalized_new["id"]
    if not offer_id:
        return False

    for idx, existing in enumerate(offers):
        if existing.get("id") == offer_id:
            merged = normalize_offer({**existing, **normalized_new})
            for field in TRACKING_FIELDS:
                merged[field] = existing.get(field, DEFAULTS[field]) or DEFAULTS[field]
            offers[idx] = merged
            return False

    offers.append(normalized_new)
    return True


def update_offer_status(
    offers: List[Dict[str, str]],
    offer_id: str,
    status: str,
    notes: Optional[str] = None,
    action_required: Optional[str] = None,
) -> bool:
    for idx, offer in enumerate(offers):
        if offer.get("id") != offer_id:
            continue

        updated = normalize_offer(offer)
        updated["status"] = status

        if notes is not None:
            updated["notes"] = notes
        if action_required is not None:
            updated["action_required"] = action_required

        offers[idx] = updated
        return True

    return False
