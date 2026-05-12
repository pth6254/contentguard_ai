"""
MEDIUM 구간 LLM tiebreaker 서비스.

ML calibrated_score가 MEDIUM 구간(기본 0.30~0.60)에 있을 때만 LLM을 호출해
LOW / MEDIUM / HIGH 중 하나로 재분류한다.

LLM_TIEBREAKER=true 환경변수로 활성화 (기본 비활성).
명확한 LOW(<0.30)·HIGH/CRITICAL(>0.60) 케이스에는 LLM을 호출하지 않아 비용·속도를 절약한다.
"""
import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """당신은 콘텐츠 안전 분류 전문가입니다.
기계학습 모델이 판단하기 애매한 MEDIUM 위험도 텍스트를 정확하게 재분류합니다.
텍스트의 실제 의도, 맥락, 표현 방식을 종합적으로 고려하세요.
반드시 유효한 JSON만 출력하세요."""

_PROMPT = """기계학습 모델이 아래 텍스트를 MEDIUM 위험도로 판정했습니다.
모델은 맥락을 이해하지 못해 오분류 가능성이 있습니다. 실제 위험도를 판단해주세요.

[텍스트]
{text}

[현재 ML 점수]
{score:.2f}  (0.0=안전, 1.0=매우위험)

[감지된 위험 카테고리]
{cats}

[적용된 규칙]
{rules}

판단 기준:
  LOW   (modifier 음수): 실제 위험 없음. 일상 과장 표현, 부정문, 보도·교육 맥락, 픽션
  MEDIUM (modifier 0):   불확실. 모니터링은 필요하나 즉각 조치 불필요
  HIGH  (modifier 양수): 명확한 위험. 운영자 즉시 검토 필요

{{"grade": "LOW"|"MEDIUM"|"HIGH", "modifier": -0.30~+0.30, "reasoning": "판단 근거 한 문장"}}"""


def tiebreak(
    text: str,
    calibrated_score: float,
    category_scores: dict[str, int],
    triggered_rules: list[dict],
) -> tuple[float, str]:
    """
    MEDIUM 구간 텍스트에 대해 LLM이 재분류하고 score modifier를 반환한다.

    반환: (modifier: -0.30 ~ +0.30, reasoning: str)
      양수 → HIGH 방향 상향, 음수 → LOW 방향 하향, 0 → 유지
    실패 시 (0.0, "") 반환 — 기존 점수 유지.
    """
    from config import settings
    from services.llm_service import _get_client

    cats  = ", ".join(k for k, v in category_scores.items() if v > 0) or "없음"
    rules = ", ".join(r.get("rule_id", "") for r in triggered_rules) or "없음"

    prompt = _PROMPT.format(
        text=text[:600],
        score=calibrated_score,
        cats=cats,
        rules=rules,
    )

    try:
        client   = _get_client("explain", no_think=settings.OLLAMA_NO_THINK_REVIEW)
        raw      = client.chat(_SYSTEM, prompt)
        start    = raw.find("{")
        end      = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON 없음")
        parsed   = json.loads(raw[start:end])
        modifier = float(parsed.get("modifier", 0.0))
        modifier = round(max(-0.30, min(0.30, modifier)), 3)
        grade    = parsed.get("grade", "MEDIUM")
        reasoning = str(parsed.get("reasoning", ""))
        logger.info(
            "Tiebreaker — score=%.3f → grade=%s modifier=%.3f  %s",
            calibrated_score, grade, modifier, reasoning,
        )
        return modifier, reasoning
    except Exception as exc:
        logger.warning("Tiebreaker 실패: %s — modifier=0 적용", exc)
        return 0.0, ""
