import concurrent.futures
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Literal

from config import settings

logger = logging.getLogger(__name__)

FALLBACK_TEMPLATES = {
    "LOW": "위험 요소가 거의 발견되지 않아 낮은 위험 등급으로 분류되었습니다. 별도 조치 없이 승인 가능합니다.",
    "MEDIUM": "스팸성 표현이나 반복 게시 등 경미한 위험 요소가 감지되었습니다. 운영 정책에 따라 모니터링이 필요할 수 있습니다.",
    "HIGH": "사기 주장, 욕설, 강한 비방 등 명확한 위험 표현이 감지되었습니다. 운영자의 직접 검토 후 조치가 필요합니다.",
    "CRITICAL": "혐오 발언, 폭력적 위협 등 심각한 위험 표현이 감지되었습니다. 즉각적인 보류 및 운영자 검토가 필요합니다.",
}

_EXTRACT_SYSTEM = "당신은 웹 콘텐츠에서 사용자 작성 텍스트를 추출하는 도우미입니다."

Task = Literal["extract", "explain"]

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)


def _extract_json(raw: str) -> str:
    """<think> 블록을 제거한 뒤 첫 번째 JSON 객체를 추출한다."""
    cleaned = _THINK_RE.sub('', raw).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        logger.error("LLM 원시 응답 (앞 400자): %s", raw[:400])
        raise ValueError("JSON 객체를 찾을 수 없음")
    return cleaned[start:end]


_CLASSIFY_SYSTEM = """당신은 콘텐츠 안전 분류 AI입니다.
텍스트를 읽고 위험도를 직접 판단해 반드시 유효한 JSON만 출력하세요.
JSON 외의 텍스트, 설명, 마크다운 코드블록을 포함하지 마세요.
텍스트에 실제로 존재하는 표현만 근거로 제시하세요."""

_CAT_NAMES = ("profanity", "threat", "sexual", "privacy", "spam", "self_harm", "policy_violation")
_CAT_KO = {
    "profanity": "욕설/비방", "threat": "협박/폭력", "sexual": "성적 표현",
    "privacy": "개인정보 침해", "spam": "스팸/도배",
    "self_harm": "자해/자살 표현", "policy_violation": "정책 위반",
}


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
        chat_kwargs: dict = {
            "model": self.model or settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self.temperature,
                "num_predict": settings.LLM_MAX_TOKENS,
            },
        }
        try:
            response = client.chat(**chat_kwargs, think=False)
        except TypeError:
            # ollama<0.6.0 환경 방어 폴백 (>=0.6.0 요구하므로 정상 환경에서는 발동 안 됨)
            response = client.chat(**chat_kwargs)
        content = response.message.content if hasattr(response, "message") else response["message"]["content"]
        return (content or "").strip()


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

def classify_and_explain(
    masked_text: str,
    category_hints: dict[str, int],
    triggered_rules: list[dict],
) -> dict:
    """
    LLM을 1차 분류기로 사용해 위험도 판정 + 설명을 1회 호출로 생성한다.
    NO_THINK 항상 활성. 키워드 전부 0점 + 규칙 없으면 LLM 호출 생략.
    실패 시 keyword 기반 fallback 반환.

    Returns dict with keys:
        risk_level, risk_score, category_scores,
        summary, score_explanation, main_reasons,
        evidence, recommended_operator_check, confidence_note
    """
    hint_summary = ", ".join(
        f"{_CAT_KO.get(k, k)}({v}점)"
        for k, v in sorted(category_hints.items(), key=lambda x: x[1], reverse=True)
        if v > 0
    ) or "없음"

    rule_summary = "\n".join(
        f"  - [{r.get('rule_id')}] {r.get('description')}"
        for r in triggered_rules
    ) or "  없음"

    prompt = f"""[분석 대상 텍스트]
{masked_text[:800]}

[키워드 탐지 힌트 — 맥락 무시한 단순 키워드 매칭, 참고만 하세요]
{hint_summary}

[강제 승격 규칙 적용 여부]
{rule_summary}

[등급 기준]
LOW:      0.00–0.29  (위험 요소 없거나 매우 경미)
MEDIUM:   0.30–0.59  (모호한 표현, 특정 대상 없는 일반적 불쾌 표현)
HIGH:     0.60–0.84  (명확한 욕설·위협·혐오, 특정인 외모·신체·성격 비하, 스팸·홍보성 콘텐츠, 범죄 행위 묘사·조장·권유, 운영자 검토 필요)
CRITICAL: 0.85–1.00  (즉각적 신체 위협·자해·심각한 범죄 표현, 사기성 사이트 링크·이미지 첨부 스팸으로 금전적 피해 유발 가능성이 확인된 경우)

[판단 원칙]
- 피해자 신고·뉴스 인용·교육 목적은 위험도를 낮게 판단
- 협박·자살 표현이 제3자 인용인지 당사자 발화인지 구분
- 키워드가 있어도 맥락상 무해하면 LOW로 판단 가능
- 스팸·홍보성 콘텐츠는 단순 도배라도 HIGH에서 시작하고, 구체적 외부 링크·이미지 첨부와 함께 사기성 사이트 연결 또는 허위 정보로 금전적 피해를 유발한다고 판단되면 CRITICAL로 분류

아래 JSON 형식으로만 출력하세요:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_score": 0.0~1.0,
  "category_scores": {{"profanity": 0~100, "threat": 0~100, "sexual": 0~100, "privacy": 0~100, "spam": 0~100, "self_harm": 0~100, "policy_violation": 0~100}},
  "summary": "등급과 핵심 이유를 담은 한 문장",
  "score_explanation": "이 점수가 이 등급인 구체적 이유",
  "main_reasons": ["이유1", "이유2"],
  "evidence": [{{"quote": "verbatim 인용", "category": "영문 카테고리명", "why_it_matters": "왜 위험한지"}}],
  "recommended_operator_check": "운영자가 확인해야 할 사항",
  "confidence_note": "불확실성 또는 오탐 가능성"
}}"""

    client = _get_client("explain")
    try:
        raw = client.chat(_CLASSIFY_SYSTEM, prompt)
        parsed = json.loads(_extract_json(raw))

        if parsed.get("risk_level") not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise ValueError(f"잘못된 risk_level: {parsed.get('risk_level')}")
        risk_score = float(parsed.get("risk_score", 0.0))
        if not 0.0 <= risk_score <= 1.0:
            raise ValueError(f"risk_score 범위 초과: {risk_score}")

        parsed["risk_score"] = round(risk_score, 3)
        raw_cats = parsed.get("category_scores", {})
        parsed["category_scores"] = {
            c: max(0, min(100, int(raw_cats.get(c, 0)))) for c in _CAT_NAMES
        }
        parsed.setdefault("summary", "")
        parsed.setdefault("score_explanation", "")
        parsed.setdefault("main_reasons", [])
        parsed.setdefault("evidence", [])
        parsed.setdefault("recommended_operator_check", "")
        parsed.setdefault("confidence_note", "")

        logger.info(
            "LLM 분류 완료 — provider=%s level=%s score=%.3f",
            settings.LLM_PROVIDER_EXPLAIN, parsed["risk_level"], parsed["risk_score"],
        )
        return parsed
    except Exception as e:
        logger.error("LLM 분류 실패: %s — fallback 사용", e)
        return _classify_fallback(category_hints, triggered_rules)


def _classify_fallback(category_hints: dict[str, int], triggered_rules: list[dict]) -> dict:
    """LLM 분류 실패 시 keyword 점수 기반 폴백."""
    max_cat = max(category_hints.values(), default=0)
    if triggered_rules or max_cat >= 85:
        risk_score, risk_level = 0.90, "CRITICAL"
    elif max_cat >= 60:
        risk_score, risk_level = 0.72, "HIGH"
    elif max_cat >= 30:
        risk_score, risk_level = 0.45, "MEDIUM"
    else:
        risk_score, risk_level = 0.10, "LOW"

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "category_scores": {c: category_hints.get(c, 0) for c in _CAT_NAMES},
        "summary": FALLBACK_TEMPLATES.get(risk_level, ""),
        "score_explanation": "",
        "main_reasons": [],
        "evidence": [],
        "recommended_operator_check": "",
        "confidence_note": "LLM 분류 실패로 키워드 기반 폴백 사용",
    }


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
