import json
import logging
from abc import ABC, abstractmethod
from typing import Literal

from config import settings

logger = logging.getLogger(__name__)

LEVEL_KO = {
    "LOW": "낮음", "MEDIUM": "보통", "HIGH": "높음", "CRITICAL": "심각",
}
ACTION_KO = {
    "APPROVE": "승인", "MONITOR": "모니터링", "REVIEW": "검토", "HOLD": "보류",
}
FALLBACK_TEMPLATES = {
    "LOW": "위험 요소가 거의 발견되지 않아 낮은 위험 등급으로 분류되었습니다. 별도 조치 없이 승인 가능합니다.",
    "MEDIUM": "스팸성 표현이나 반복 게시 등 경미한 위험 요소가 감지되었습니다. 운영 정책에 따라 모니터링이 필요할 수 있습니다.",
    "HIGH": "사기 주장, 욕설, 강한 비방 등 명확한 위험 표현이 감지되었습니다. 운영자의 직접 검토 후 조치가 필요합니다.",
    "CRITICAL": "혐오 발언, 폭력적 위협 등 심각한 위험 표현이 감지되었습니다. 즉각적인 보류 및 운영자 검토가 필요합니다.",
}

_EXPLAIN_SYSTEM = "당신은 콘텐츠 안전 운영자를 돕는 AI 어시스턴트입니다. 분석 결과를 간결하고 명확하게 한국어로 설명해주세요."
_EXPLAIN_JSON_SYSTEM = """당신은 콘텐츠 안전 심사를 지원하는 AI 분석가입니다.
점수와 등급은 이미 확정되었으며, 당신은 그 결과를 해설하는 역할만 합니다.
반드시 유효한 JSON만 출력하세요. JSON 외의 텍스트(설명, 마크다운 코드블록 등)를 포함하지 마세요.
텍스트에 실제로 존재하는 표현만 근거로 제시하고, 개인정보(전화번호·이메일·주민번호 등)를 설명에 포함하지 마세요."""
_EXTRACT_SYSTEM = "당신은 웹 콘텐츠에서 사용자 작성 텍스트를 추출하는 도우미입니다."

Task = Literal["extract", "explain"]


# ── 공급자 추상 인터페이스 ──────────────────────────────────────────────────

class _LLMClient(ABC):
    def __init__(self, model: str = "", temperature: float = 0.1) -> None:
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def chat(self, system: str, user: str) -> str: ...


# ── 공급자별 구현 ──────────────────────────────────────────────────────────

class _OllamaClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        response = client.chat(
            model=self.model or settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": self.temperature},
        )
        return response["message"]["content"].strip()


class _OpenAIClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=self.model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
        )
        return response.choices[0].message.content.strip()


class _AnthropicClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=self.model or "claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=self.temperature,
        )
        return response.content[0].text.strip()


class _GeminiClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=self.model or "gemini-2.0-flash",
            system_instruction=system,
        )
        response = model.generate_content(
            user,
            generation_config=genai.types.GenerationConfig(temperature=self.temperature),
        )
        return response.text.strip()


class _DeepSeekClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
        response = client.chat.completions.create(
            model=self.model or "deepseek-chat",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=self.temperature,
        )
        return response.choices[0].message.content.strip()


_PROVIDERS: dict[str, type[_LLMClient]] = {
    "ollama":    _OllamaClient,
    "openai":    _OpenAIClient,
    "anthropic": _AnthropicClient,
    "gemini":    _GeminiClient,
    "deepseek":  _DeepSeekClient,
}


# ── 작업별 프로바이더·모델 해석 ───────────────────────────────────────────

def _get_client(task: Task) -> _LLMClient:
    """task에 맞는 프로바이더·모델·temperature로 클라이언트를 생성한다."""
    if task == "extract":
        provider    = settings.LLM_PROVIDER_EXTRACT
        model       = settings.LLM_MODEL_EXTRACT
        temperature = settings.LLM_TEMPERATURE_EXTRACT
    else:  # explain
        provider    = settings.LLM_PROVIDER_EXPLAIN
        model       = settings.LLM_MODEL_EXPLAIN
        temperature = settings.LLM_TEMPERATURE_EXPLAIN

    cls = _PROVIDERS.get(provider.lower())
    if cls is None:
        raise ValueError(
            f"지원하지 않는 LLM 프로바이더 ({task}): '{provider}'. 지원값: {list(_PROVIDERS)}"
        )
    return cls(model=model, temperature=temperature)


# ── 공개 인터페이스 ────────────────────────────────────────────────────────

def generate_explanation(
    text: str,
    risk_score: float,
    risk_level: str,
    recommended_action: str,
) -> str:
    prompt = f"""다음은 콘텐츠 위험도 분석 결과입니다.

텍스트: {text}
위험 점수: {risk_score:.2f} (0.0 = 안전, 1.0 = 매우 위험)
위험 등급: {risk_level} ({LEVEL_KO[risk_level]})
권장 조치: {recommended_action} ({ACTION_KO[recommended_action]})

운영자가 최종 판단을 내릴 수 있도록 아래 내용을 포함해 2~3문장으로 한국어로 설명하세요.
- 어떤 표현이나 내용이 위험 요소로 작용했는지
- 왜 이 등급으로 분류되었는지
- 운영자에게 어떤 판단을 권장하는지"""

    client = _get_client("explain")
    try:
        explanation = client.chat(_EXPLAIN_SYSTEM, prompt)
        logger.info(
            "LLM 설명 생성 완료 — provider=%s model=%s level=%s",
            settings.LLM_PROVIDER_EXPLAIN, client.model or "(default)", risk_level,
        )
        return explanation
    except Exception as e:
        logger.error(
            "LLM 설명 생성 실패 (provider=%s model=%s): %s — 기본 설명 반환",
            settings.LLM_PROVIDER_EXPLAIN, client.model or "(default)", e,
        )
        return FALLBACK_TEMPLATES.get(risk_level, "분석 결과를 확인하세요.")


def generate_explanation_json(
    masked_text: str,
    final_score: float,
    final_grade: str,
    recommended_action: str,
    category_scores: dict[str, int],
    triggered_rules: list[dict],
    evidence_spans: list[dict],
    context_note: str = "",
) -> dict:
    """
    LLM을 해설자로만 사용해 구조화된 JSON 설명을 생성한다.
    점수/등급은 이미 확정된 값이며 LLM은 변경할 수 없다.
    실패 또는 검증 실패 시 fallback을 반환한다.
    """
    from services.explanation_validator import validate_explanation, build_fallback_explanation

    cat_ko = {
        "profanity": "욕설/비방", "threat": "협박/폭력", "sexual": "성적 표현",
        "privacy": "개인정보 침해", "spam": "스팸/도배",
        "self_harm": "자해/자살 표현", "policy_violation": "정책 위반",
    }
    grade_ko = {
        "LOW": "낮음", "MEDIUM": "보통", "HIGH": "높음", "CRITICAL": "심각",
    }
    action_ko = {
        "APPROVE": "승인", "MONITOR": "모니터링", "REVIEW": "검토", "HOLD": "보류",
    }

    cat_summary = ", ".join(
        f"{cat_ko.get(k, k)}({v}점)"
        for k, v in sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ) or "없음"

    rule_summary = "\n".join(
        f"  - [{r.get('rule_id')}] {r.get('description')} (최소 등급: {r.get('min_grade')})"
        for r in triggered_rules
    ) or "  없음"

    span_summary = "\n".join(
        f"  - \"{s.get('text')}\" ({cat_ko.get(s.get('category', ''), s.get('category', ''))}, 심각도: {s.get('severity')})"
        for s in evidence_spans
    ) or "  없음"

    context_section = f"\n[맥락 분석 결과]\n{context_note}\n" if context_note else ""

    prompt = f"""다음은 콘텐츠 안전 시스템의 분석 결과입니다.
{context_section}
[분석 대상 텍스트]
{masked_text}

[확정된 판정 결과 — 변경 불가]
최종 점수: {final_score:.3f} (0.0=안전, 1.0=매우위험)
최종 등급: {final_grade} ({grade_ko.get(final_grade, final_grade)})
권장 조치: {recommended_action} ({action_ko.get(recommended_action, recommended_action)})

[카테고리별 위험 점수 (0-100)]
{cat_summary}

[강제 승격 규칙 적용 결과]
{rule_summary}

[감지된 위험 표현]
{span_summary}

위 분석 결과를 바탕으로 운영자를 위한 심사 리포트를 다음 JSON 형식으로 작성하세요.
최종 점수와 등급은 절대 변경하지 마세요. 텍스트에 실제로 있는 표현만 근거로 제시하세요.

{{
  "summary": "한 문장 요약",
  "score_explanation": "이 점수와 등급이 산정된 이유 설명",
  "main_reasons": ["핵심 이유 1", "핵심 이유 2"],
  "evidence": [
    {{
      "quote": "텍스트에서 인용한 위험 표현",
      "category": "카테고리명(영문)",
      "why_it_matters": "왜 위험한지 설명"
    }}
  ],
  "recommended_operator_check": "운영자가 반드시 확인해야 할 사항",
  "confidence_note": "판단의 확신도 또는 주의사항"
}}"""

    client = _get_client("explain")
    try:
        raw = client.chat(_EXPLAIN_JSON_SYSTEM, prompt)
        # JSON 블록만 추출
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("JSON 객체를 찾을 수 없음")
        parsed = json.loads(raw[start:end])
    except Exception as e:
        logger.error(
            "LLM JSON 설명 생성 실패 (provider=%s): %s — fallback 사용",
            settings.LLM_PROVIDER_EXPLAIN, e,
        )
        return build_fallback_explanation(
            final_grade, final_score, category_scores, triggered_rules, recommended_action
        )

    is_valid, errors = validate_explanation(parsed, final_grade, final_score, masked_text)
    if not is_valid:
        logger.warning("LLM 설명 검증 실패: %s — fallback 사용", errors)
        return build_fallback_explanation(
            final_grade, final_score, category_scores, triggered_rules, recommended_action
        )

    logger.info(
        "LLM JSON 설명 생성 완료 — provider=%s grade=%s",
        settings.LLM_PROVIDER_EXPLAIN, final_grade,
    )
    return parsed


_MIN_TEXT_LEN = 10   # 날짜·작성자명 등 제거
_MAX_TEXT_LEN = 600  # 기사 본문 등 제거

_COMMENT_PATTERNS = frozenset({
    "comment", "review", "reply", "feedback", "testimonial",
    "opinion", "rating", "discussion", "response", "ugc",
})


def _extract_with_beautifulsoup(html: str, max_items: int) -> list[str]:
    """CSS 클래스/ID에서 댓글·리뷰 패턴을 탐지해 사용자 작성 텍스트를 추출한다."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    def _matches(tag) -> bool:
        combined = (" ".join(tag.get("class", [])) + " " + tag.get("id", "")).lower()
        return any(p in combined for p in _COMMENT_PATTERNS)

    results = []
    for element in soup.find_all(_matches):
        # 매칭된 자식 요소가 있으면 부모는 건너뜀 (가장 작은 단위만 추출)
        if any(_matches(child) for child in element.find_all(True)):
            continue
        text = element.get_text(separator=" ", strip=True)
        if _MIN_TEXT_LEN <= len(text) <= _MAX_TEXT_LEN:
            results.append(text)

    seen: set[str] = set()
    unique = [t for t in results if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]
    return unique[:max_items]


def _extract_with_trafilatura(html: str, max_items: int) -> list[str]:
    """Trafilatura로 HTML에서 사용자 작성 텍스트를 빠르게 추출한다."""
    import trafilatura
    text = trafilatura.extract(html, include_comments=True, include_tables=False)
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    items = [ln for ln in lines if _MIN_TEXT_LEN <= len(ln) <= _MAX_TEXT_LEN]
    return items[:max_items]


def _is_quality_sufficient(items: list[str], max_items: int) -> bool:
    """추출 결과가 LLM 폴백 없이 충분한지 판단한다."""
    if len(items) < max(2, max_items // 3):
        return False
    avg_len = sum(len(t) for t in items) / len(items)
    return 20 <= avg_len <= 300  # 너무 짧으면 메타데이터, 너무 길면 기사 본문


def _extract_with_llm(markdown: str, max_items: int) -> list[str]:
    """LLM으로 마크다운에서 사용자 작성 텍스트를 추출한다."""
    prompt = f"""다음은 웹페이지를 마크다운으로 변환한 내용입니다.
사용자가 직접 작성한 댓글, 리뷰, 게시글 본문만 추출하세요.
메뉴, 광고, 버튼, 날짜, 작성자명 등 부가 정보는 제외하세요.
최대 {max_items}개를 JSON 문자열 배열로만 반환하세요. 설명 없이 배열만 출력하세요.

출력 형식:
["텍스트1", "텍스트2", "텍스트3"]

마크다운:
{markdown[:6000]}"""

    client = _get_client("extract")
    logger.info(
        "텍스트 추출 (LLM) — provider=%s model=%s",
        settings.LLM_PROVIDER_EXTRACT, client.model or "(default)",
    )
    content = client.chat(_EXTRACT_SYSTEM, prompt)
    start = content.find("[")
    end = content.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("JSON 배열을 찾을 수 없습니다.")
    return json.loads(content[start:end])


def extract_texts(html: str, markdown: str, max_items: int) -> tuple[list[str], str]:
    """
    3단계 하이브리드 추출.
    1차 BeautifulSoup (comment/review CSS 패턴) → 2차 Trafilatura → 3차 LLM 폴백.
    반환: (texts, method)
    """
    # 1차: BeautifulSoup — 댓글·리뷰 클래스 직접 탐지
    items = _extract_with_beautifulsoup(html, max_items)
    if items:
        logger.info("텍스트 추출 완료 — method=beautifulsoup count=%d", len(items))
        return items, "beautifulsoup"

    # 2차: Trafilatura — 범용 본문 추출
    items = _extract_with_trafilatura(html, max_items)
    if _is_quality_sufficient(items, max_items):
        logger.info("텍스트 추출 완료 — method=trafilatura count=%d", len(items))
        return items, "trafilatura"

    # 3차: LLM 폴백
    logger.info("Trafilatura 품질 부족 (count=%d) → LLM 폴백", len(items))
    items = _extract_with_llm(markdown, max_items)
    return items, "llm"
