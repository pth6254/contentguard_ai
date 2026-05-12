"""
LLM 맥락 검토 서비스.

키워드/ML 기반 점수 산정 이후, LLM이 텍스트 의도를 평가해
calibrated_score를 최대 -0.30 조정하는 modifier를 반환한다.

LLM_CONTEXT_REVIEW=true 환경변수로 활성화 (기본 비활성).
"""
import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM = """당신은 콘텐츠 안전 시스템의 맥락 분석기입니다.
키워드 기반 탐지는 뉴스·교육·부정문 등에서 오탐을 일으킵니다.
텍스트의 실제 의도를 파악해 위험도 조정이 필요한지 판단하세요.
반드시 유효한 JSON만 출력하세요. JSON 외 텍스트는 포함하지 마세요."""

_PROMPT_TEMPLATE = """다음 텍스트가 콘텐츠 안전 시스템에서 위험 신호를 감지했습니다.

[텍스트]
{text}

[감지된 위험 카테고리]
{flagged_cats}

[적용된 강제 승격 규칙]
{rule_names}

텍스트의 실제 의도를 분석하고 다음 JSON을 반환하세요.

modifier 기준:
  -0.30: 명백히 무해한 맥락 (뉴스 보도, 예방 캠페인, 학술·교육 자료)
  -0.20: 부정문 또는 조건부 표현으로 실제 위험이 낮음
  -0.10: 일상적 과장 표현 (죽겠다, 미치겠다 등 관용어)
   0.00: 실제 위험한 의도이거나 판단 불가

{{"modifier": 0.00 ~ -0.30 사이 숫자, "note": "맥락 분석 결과 한 문장"}}"""

_MODIFIER_MIN = -0.30
_MODIFIER_MAX = 0.0


def review_context(
    text: str,
    category_scores: dict[str, int],
    triggered_rules: list[dict],
) -> tuple[float, str]:
    """
    LLM으로 텍스트 의도를 분석해 위험도 조정 계수를 반환한다.

    반환: (modifier: -0.30 ~ 0.00, note: str)
    실패 시 (0.0, "") 반환 — 점수 변경 없음.
    """
    from config import settings
    from services.llm_service import _get_client

    flagged = ", ".join(k for k, v in category_scores.items() if v > 0) or "없음"
    rules   = ", ".join(r.get("rule_id", "") for r in triggered_rules) or "없음"

    prompt = _PROMPT_TEMPLATE.format(
        text=text[:800],
        flagged_cats=flagged,
        rule_names=rules,
    )

    try:
        client = _get_client("explain", no_think=settings.OLLAMA_NO_THINK_REVIEW)
        raw    = client.chat(_SYSTEM, prompt)
        start  = raw.find("{")
        end    = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON 없음")
        parsed   = json.loads(raw[start:end])
        modifier = float(parsed.get("modifier", 0.0))
        modifier = round(max(_MODIFIER_MIN, min(_MODIFIER_MAX, modifier)), 3)
        note     = str(parsed.get("note", ""))
        logger.info("Context review — modifier=%.3f note=%s", modifier, note)
        return modifier, note
    except Exception as exc:
        logger.warning("Context review 실패: %s — modifier=0 적용", exc)
        return 0.0, ""
