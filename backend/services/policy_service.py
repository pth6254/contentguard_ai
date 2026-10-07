"""A customer policy may escalate or require review; it never weakens global rules."""
from models import ClientPolicy
from services.decision_policy_service import get_recommended_action
from services.decision_policy_service import classify_risk_level

ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
FLOOR = {"LOW": 0.0, "MEDIUM": 0.3, "HIGH": 0.6, "CRITICAL": 0.85}


def base_decision(record):
    details = record.explanation_json or {}
    if details.get("base_decision"):
        return details["base_decision"]
    # Recover older analyses only when both the model score and rules exist.
    if record.calibrated_score is None or record.triggered_rules is None:
        return None
    score = record.calibrated_score
    grade = classify_risk_level(score)
    for rule in record.triggered_rules:
        minimum = rule.get("min_grade")
        if not rule.get("review_only") and minimum in ORDER and ORDER.index(minimum) > ORDER.index(grade):
            grade = minimum
    return {"risk_score": max(score, FLOOR[grade]), "risk_level": grade,
            "review_required": details.get("analysis_status") != "completed" or any(r.get("review_only") for r in record.triggered_rules)}


def load_policy(db, client_id: int | None) -> dict | None:
    if client_id is None:
        return None
    policy = db.query(ClientPolicy).filter(ClientPolicy.client_id == client_id).first()
    return ({"version": policy.version, "category_min_levels": policy.category_min_levels,
             "review_categories": policy.review_categories, "trigger_score": policy.trigger_score}
            if policy else None)


def apply_policy(score: float, grade: str, categories: dict[str, int], policy: dict | None) -> tuple[float, str, str, bool, str]:
    if not policy:
        return score, grade, get_recommended_action(grade), False, ""
    cutoff = policy["trigger_score"]
    promoted = []
    for category, minimum in policy["category_min_levels"].items():
        if categories.get(category, 0) >= cutoff and ORDER.index(minimum) > ORDER.index(grade):
            grade = minimum
            promoted.append(category)
    review = any(categories.get(category, 0) >= cutoff for category in policy["review_categories"])
    score = max(score, FLOOR[grade])
    note = f"고객 정책 v{policy['version']}에 따라 {', '.join(promoted)} 최소 등급을 적용했습니다. " if promoted else ""
    return score, grade, get_recommended_action(grade), review, note
