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
_EXTRACT_SYSTEM = "당신은 웹 콘텐츠에서 사용자 작성 텍스트를 추출하는 도우미입니다."

Task = Literal["extract", "explain"]


# ── 공급자 추상 인터페이스 ──────────────────────────────────────────────────

class _LLMClient(ABC):
    def __init__(self, model: str = "") -> None:
        self.model = model

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
            options={"temperature": 0.3},
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
            temperature=0.3,
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
            generation_config=genai.types.GenerationConfig(temperature=0.3),
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
            temperature=0.3,
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
    """task에 맞는 프로바이더와 모델로 클라이언트를 생성한다."""
    if task == "extract":
        provider = settings.LLM_PROVIDER_EXTRACT
        model    = settings.LLM_MODEL_EXTRACT
    else:  # explain
        provider = settings.LLM_PROVIDER_EXPLAIN
        model    = settings.LLM_MODEL_EXPLAIN

    cls = _PROVIDERS.get(provider.lower())
    if cls is None:
        raise ValueError(
            f"지원하지 않는 LLM 프로바이더 ({task}): '{provider}'. 지원값: {list(_PROVIDERS)}"
        )
    return cls(model=model)


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
