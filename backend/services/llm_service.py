import json
import logging
from abc import ABC, abstractmethod

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


# ── 공급자 추상 인터페이스 ──────────────────────────────────────────────────

class _LLMClient(ABC):
    @abstractmethod
    def chat(self, system: str, user: str) -> str: ...


# ── 공급자별 구현 ──────────────────────────────────────────────────────────

class _OllamaClient(_LLMClient):
    def chat(self, system: str, user: str) -> str:
        import ollama
        client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        response = client.chat(
            model=settings.LLM_MODEL or settings.OLLAMA_MODEL,
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
            model=settings.LLM_MODEL or "gpt-4o-mini",
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
            model=settings.LLM_MODEL or "claude-haiku-4-5-20251001",
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
            model_name=settings.LLM_MODEL or "gemini-2.0-flash",
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
            model=settings.LLM_MODEL or "deepseek-chat",
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


def _get_client() -> _LLMClient:
    provider = settings.LLM_PROVIDER.lower()
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise ValueError(
            f"지원하지 않는 LLM_PROVIDER: '{provider}'. 지원값: {list(_PROVIDERS)}"
        )
    return cls()


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

    try:
        explanation = _get_client().chat(_EXPLAIN_SYSTEM, prompt)
        logger.info("LLM 설명 생성 완료 — provider=%s level=%s", settings.LLM_PROVIDER, risk_level)
        return explanation
    except Exception as e:
        logger.error("LLM 호출 실패 (provider=%s): %s — 기본 설명 반환", settings.LLM_PROVIDER, e)
        return FALLBACK_TEMPLATES.get(risk_level, "분석 결과를 확인하세요.")


def extract_texts(markdown: str, max_items: int) -> list[str]:
    """마크다운에서 사용자 작성 텍스트를 LLM으로 추출한다."""
    prompt = f"""다음은 웹페이지를 마크다운으로 변환한 내용입니다.
사용자가 직접 작성한 댓글, 리뷰, 게시글 본문만 추출하세요.
메뉴, 광고, 버튼, 날짜, 작성자명 등 부가 정보는 제외하세요.
최대 {max_items}개를 JSON 문자열 배열로만 반환하세요. 설명 없이 배열만 출력하세요.

출력 형식:
["텍스트1", "텍스트2", "텍스트3"]

마크다운:
{markdown[:6000]}"""

    content = _get_client().chat(_EXTRACT_SYSTEM, prompt)
    start = content.find("[")
    end = content.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("JSON 배열을 찾을 수 없습니다.")
    return json.loads(content[start:end])
