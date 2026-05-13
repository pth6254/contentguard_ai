"""
HIGH/CRITICAL 콘텐츠 LLM 심층 분석 서비스.

ML·규칙이 제공하지 못하는 의도·위험성 판단을 LLM이 수행한다:
  - 특정 대상 여부 (is_targeted)
  - 즉각적 위험 여부 (is_immediate)
  - 실행 가능성 (actionability)
  - 위협 대상 설명 (target_description)
  - 운영자 권장 조치 (suggested_action)

LLM_DEEP_ANALYSIS=true 환경변수로 활성화 (기본 비활성).
HIGH/CRITICAL 케이스에서만 호출해 비용 부담을 제한한다.
"""
import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """당신은 콘텐츠 안전 전문 분석가입니다.
위험 판정이 내려진 콘텐츠를 심층 분석해 운영자의 의사결정을 지원합니다.
반드시 유효한 JSON만 출력하세요. JSON 외 텍스트는 포함하지 마세요."""

_PROMPT = """다음 콘텐츠가 {grade} 위험 등급으로 판정되었습니다.
운영자가 최종 조치를 결정하는 데 필요한 심층 분석을 수행하세요.

[콘텐츠]
{text}

[감지된 위험 카테고리]
{cats}

[적용된 규칙]
{rules}

[감지된 위험 표현]
{spans}

분석 항목:
1. is_targeted    : 특정 개인·집단을 향한 위협인가? (true/false)
2. is_immediate   : 즉각적·실질적 위험인가? (true/false)
3. actionability  : 위협 실행 가능성 — "low"|"medium"|"high"
4. target_description : 위협 대상 설명. 불특정이면 "불특정"
5. suggested_action   : 운영자 권장 조치 (구체적 한 문장)

{{
  "is_targeted": true/false,
  "is_immediate": true/false,
  "actionability": "low"|"medium"|"high",
  "target_description": "...",
  "suggested_action": "..."
}}"""


def analyze_deeply(
    text: str,
    final_grade: str,
    category_scores: dict[str, int],
    triggered_rules: list[dict],
    evidence_spans: list[dict],
) -> dict | None:
    """
    HIGH/CRITICAL 콘텐츠에 대해 LLM 심층 분석을 수행한다.
    실패 시 None 반환 — 호출자는 None을 그대로 전달하면 됨.
    """
    from config import settings
    from services.llm_service import _get_client

    cats  = ", ".join(k for k, v in category_scores.items() if v > 0) or "없음"
    rules = ", ".join(r.get("rule_id", "") for r in triggered_rules) or "없음"
    spans = ", ".join(f'"{s.get("text")}"' for s in evidence_spans[:3]) or "없음"

    prompt = _PROMPT.format(
        grade=final_grade,
        text=text[:600],
        cats=cats,
        rules=rules,
        spans=spans,
    )

    try:
        client = _get_client("explain")
        raw    = client.chat(_SYSTEM, prompt)
        start  = raw.find("{")
        end    = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON 없음")
        parsed = json.loads(raw[start:end])
        result = {
            "is_targeted":        bool(parsed.get("is_targeted", False)),
            "is_immediate":       bool(parsed.get("is_immediate", False)),
            "actionability":      str(parsed.get("actionability", "low")),
            "target_description": str(parsed.get("target_description", "불특정")),
            "suggested_action":   str(parsed.get("suggested_action", "")),
        }
        logger.info(
            "Deep analysis — grade=%s targeted=%s immediate=%s actionability=%s",
            final_grade, result["is_targeted"], result["is_immediate"], result["actionability"],
        )
        return result
    except Exception as exc:
        logger.warning("Deep analysis 실패: %s", exc)
        return None
