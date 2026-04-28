import logging
import re
from typing import Dict, List, Optional, Tuple

import criteria
from storage import load_offers, normalize_offer, save_offers

LOGGER_NAME = "offers_evaluator"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def contains_any(text: str, terms: List[str]) -> List[str]:
    matches: List[str] = []
    for term in terms:
        if normalize_text(term) and normalize_text(term) in text:
            matches.append(term)
    return matches


def extract_salary(text: str) -> Optional[int]:
    # Captura números de 5+ dígitos, con separadores comunes.
    candidates = re.findall(r"\b\d{1,3}(?:[\.,]\d{3})+\b|\b\d{5,}\b", text)
    parsed: List[int] = []
    for token in candidates:
        cleaned = re.sub(r"[^\d]", "", token)
        if not cleaned:
            continue
        value = int(cleaned)
        if value >= 50000:
            parsed.append(value)

    if not parsed:
        return None

    return max(parsed)


def category_from_score(score: int) -> str:
    if score >= 80:
        return "ideal"
    if score >= 60:
        return "posible"
    if score >= 40:
        return "dudosa"
    return "descartada"


def action_from_category(category: str) -> str:
    mapping = {
        "ideal": "lista_para_revisar",
        "posible": "revisar",
        "dudosa": "pendiente_manual",
        "descartada": "descartar",
    }
    return mapping[category]


def evaluate_offer(offer: Dict[str, str]) -> Tuple[int, str]:
    weights = criteria.flexible_criteria.get("weights", {})
    desired_weight = int(weights.get("desired_keywords", 35))
    secondary_weight = int(weights.get("secondary_keywords", 15))
    location_weight = int(weights.get("location", 20))
    modality_weight = int(weights.get("modality", 10))
    salary_weight = int(weights.get("salary", 10))
    seniority_weight = int(weights.get("seniority", 10))
    forbidden_penalty = int(criteria.flexible_criteria.get("forbidden_penalty", 40))

    title = normalize_text(offer.get("title"))
    company = normalize_text(offer.get("company"))
    location = normalize_text(offer.get("location"))
    blob = " ".join([title, company, location])

    score = 0
    notes_parts: List[str] = []

    desired_matches = contains_any(blob, criteria.desired_keywords)
    if desired_matches:
        ratio = min(len(desired_matches), len(criteria.desired_keywords)) / max(len(criteria.desired_keywords), 1)
        score += round(desired_weight * ratio)
        notes_parts.append(f"keywords principales: {', '.join(desired_matches[:3])}")
    else:
        notes_parts.append("sin keywords principales")

    secondary_matches = contains_any(blob, criteria.secondary_keywords)
    if secondary_matches:
        ratio = min(len(secondary_matches), len(criteria.secondary_keywords)) / max(len(criteria.secondary_keywords), 1)
        score += round(secondary_weight * ratio)
        notes_parts.append(f"keywords secundarias: {', '.join(secondary_matches[:3])}")

    forbidden_matches = contains_any(blob, criteria.forbidden_keywords)
    if forbidden_matches:
        score -= forbidden_penalty
        notes_parts.append(f"keywords prohibidas detectadas: {', '.join(forbidden_matches[:3])}")

    location_matches = contains_any(location, criteria.desired_locations)
    if location_matches:
        score += location_weight
        notes_parts.append(f"ubicación alineada: {location_matches[0]}")
    elif not criteria.flexible_criteria.get("allow_unknown_location", True):
        score -= round(location_weight / 2)
        notes_parts.append("ubicación no alineada")

    modality_matches = contains_any(blob, criteria.desired_modalities)
    if modality_matches:
        score += modality_weight
        notes_parts.append(f"modalidad alineada: {modality_matches[0]}")
    elif not criteria.flexible_criteria.get("allow_unknown_modality", True):
        score -= round(modality_weight / 2)
        notes_parts.append("modalidad no indicada")

    salary = extract_salary(blob)
    if salary is not None:
        if salary >= criteria.minimum_salary:
            score += salary_weight
            notes_parts.append(f"salario detectado >= mínimo ({salary})")
        else:
            score -= round(salary_weight / 2)
            notes_parts.append(f"salario detectado < mínimo ({salary})")
    elif not criteria.flexible_criteria.get("allow_missing_salary", True):
        score -= round(salary_weight / 2)
        notes_parts.append("sin salario explícito")

    seniority_matches = contains_any(title, criteria.desired_seniority)
    if seniority_matches:
        score += seniority_weight
        notes_parts.append(f"seniority alineada: {seniority_matches[0]}")

    score = max(0, min(100, score))
    notes = " | ".join(notes_parts)
    return score, notes


def evaluate_offers() -> None:
    logger = setup_logging()
    offers = load_offers()
    logger.info("Ofertas cargadas para evaluar: %s", len(offers))

    updated_offers: List[Dict[str, str]] = []

    for idx, offer in enumerate(offers):
        try:
            normalized = normalize_offer(offer)
            score, auto_notes = evaluate_offer(normalized)
            category = category_from_score(score)
            action_required = action_from_category(category)

            normalized["score"] = str(score)
            normalized["category"] = category
            normalized["action_required"] = action_required
            normalized["status"] = "evaluada"

            existing_notes = (normalized.get("notes") or "").strip()
            if not existing_notes:
                normalized["notes"] = auto_notes

            updated_offers.append(normalized)
        except Exception as exc:
            logger.exception(
                "Error evaluando oferta idx=%s id=%s: %s",
                idx,
                offer.get("id", "sin_id"),
                exc,
            )
            updated_offers.append(normalize_offer(offer))

    save_offers(updated_offers)
    logger.info("Evaluación finalizada. Ofertas actualizadas: %s", len(updated_offers))


if __name__ == "__main__":
    evaluate_offers()
