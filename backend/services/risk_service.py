import logging

logger = logging.getLogger(__name__)

RISK_KEYWORDS: dict[str, float] = {
    "사기": 0.4,
    "쓰레기": 0.3,
    "최악": 0.3,
    "꺼져": 0.4,
    "혐오": 0.5,
    "광고": 0.2,
    "도배": 0.2,
}


def calculate_risk_score(text: str) -> float:
    score = 0.0
    for keyword, weight in RISK_KEYWORDS.items():
        if keyword in text:
            score += weight
            logger.debug("Keyword '%s' matched, adding weight %.1f", keyword, weight)
    return min(round(score, 2), 1.0)


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


def analyze_content(text: str) -> dict:
    risk_score = calculate_risk_score(text)
    risk_level = classify_risk_level(risk_score)
    recommended_action = get_recommended_action(risk_level)

    logger.info(
        "Analysis complete — score=%.2f level=%s action=%s",
        risk_score,
        risk_level,
        recommended_action,
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "recommended_action": recommended_action,
    }
