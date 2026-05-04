import logging

import ollama

from config import settings

logger = logging.getLogger(__name__)

LEVEL_KO = {
    "LOW": "낮음",
    "MEDIUM": "보통",
    "HIGH": "높음",
    "CRITICAL": "심각",
}

ACTION_KO = {
    "APPROVE": "승인",
    "MONITOR": "모니터링",
    "REVIEW": "검토",
    "HOLD": "보류",
}

FALLBACK_TEMPLATES = {
    "LOW": "위험 요소가 거의 발견되지 않아 낮은 위험 등급으로 분류되었습니다. 별도 조치 없이 승인 가능합니다.",
    "MEDIUM": "스팸성 표현이나 반복 게시 등 경미한 위험 요소가 감지되었습니다. 운영 정책에 따라 모니터링이 필요할 수 있습니다.",
    "HIGH": "사기 주장, 욕설, 강한 비방 등 명확한 위험 표현이 감지되었습니다. 운영자의 직접 검토 후 조치가 필요합니다.",
    "CRITICAL": "혐오 발언, 폭력적 위협 등 심각한 위험 표현이 감지되었습니다. 즉각적인 보류 및 운영자 검토가 필요합니다.",
}


def generate_explanation(
    text: str,
    risk_score: float,
    risk_level: str,
    recommended_action: str,
) -> str:
    try:
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)

        prompt = f"""다음은 콘텐츠 위험도 분석 결과입니다.

텍스트: {text}
위험 점수: {risk_score:.2f} (0.0 = 안전, 1.0 = 매우 위험)
위험 등급: {risk_level} ({LEVEL_KO[risk_level]})
권장 조치: {recommended_action} ({ACTION_KO[recommended_action]})

운영자가 최종 판단을 내릴 수 있도록 아래 내용을 포함해 2~3문장으로 한국어로 설명하세요.
- 어떤 표현이나 내용이 위험 요소로 작용했는지
- 왜 이 등급으로 분류되었는지
- 운영자에게 어떤 판단을 권장하는지"""

        response = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 콘텐츠 안전 운영자를 돕는 AI 어시스턴트입니다. 분석 결과를 간결하고 명확하게 한국어로 설명해주세요.",
                },
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3},
        )

        explanation = response["message"]["content"].strip()
        logger.info("LLM 설명 생성 완료 — model=%s level=%s", settings.OLLAMA_MODEL, risk_level)
        return explanation

    except Exception as e:
        logger.error("Ollama 호출 실패: %s — 기본 설명 반환", e)
        return FALLBACK_TEMPLATES.get(risk_level, "분석 결과를 확인하세요.")
