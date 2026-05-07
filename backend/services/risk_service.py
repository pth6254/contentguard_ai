import logging

logger = logging.getLogger(__name__)


def classify_risk_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.60:
        return "HIGH"
    if score >= 0.30:
        return "MEDIUM"
    return "LOW"


def get_recommended_action(risk_level: str) -> str:
    actions = {
        "LOW": "APPROVE",
        "MEDIUM": "MONITOR",
        "HIGH": "REVIEW",
        "CRITICAL": "HOLD",
    }
    return actions[risk_level]


