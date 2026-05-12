"""
PII 마스킹 + 패턴 기반 강제 승격 규칙 탐지.
LLM에 텍스트를 전달하기 전에 반드시 mask_pii()를 호출해야 한다.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── PII 마스킹 패턴 ────────────────────────────────────────────────────────

_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 더 구체적인 패턴 먼저 — 일반 패턴이 앞에 오면 부분 일치가 발생함
    (re.compile(r'(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)'), '카드번호'),
    (re.compile(r'(?<!\d)\d{6}-[1-4]\d{6}(?!\d)'), '주민번호'),
    (re.compile(r'(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)'), '전화번호'),
    (re.compile(r'(?<!\d)\d{2,3}-\d{3,4}-\d{4}(?!\d)'), '전화번호'),
    (re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'), '이메일'),
]


def mask_pii(text: str) -> tuple[str, list[str]]:
    """
    PII 패턴을 [타입] 태그로 마스킹한다.
    Returns: (masked_text, detected_pii_types)
    """
    masked = text
    detected: list[str] = []
    for pattern, label in _PII_PATTERNS:
        if pattern.search(masked):
            detected.append(label)
            masked = pattern.sub(f'[{label}]', masked)
    return masked, detected


# ── 강제 승격 규칙 패턴 ─────────────────────────────────────────────────────

@dataclass
class TriggeredRule:
    rule_id: str
    description: str
    min_grade: str      # 이 규칙이 요구하는 최소 등급
    category: str       # 위험 카테고리
    matched_text: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "min_grade": self.min_grade,
            "category": self.category,
            "matched_text": self.matched_text,
        }


_THREAT_RE = re.compile(
    r'(죽여버릴|죽이겠다|살해할|찾아가서.{0,10}(?:혼내|때려|죽여|해치)|'
    r'폭탄|테러|죽어버려|없애버릴|불태워|처단할)',
    re.I,
)
_SELF_HARM_RE = re.compile(
    r'(자살할|스스로 목숨|죽고 싶다|삶을 끝내|더 이상 살고 싶지|자해할|목숨을 끊)',
    re.I,
)
_PHISHING_RE = re.compile(
    r'https?://\S+(?:login|verify|account|secure|banking|update)\S*',
    re.I,
)
_DOXXING_RE = re.compile(
    r'(신상털|집주소\s*(?:알아냈|공개|올려)|개인정보\s*(?:공개|유출))',
    re.I,
)


def detect_rules(text: str, detected_pii: list[str]) -> list[TriggeredRule]:
    """
    텍스트와 PII 탐지 결과를 받아 강제 승격 규칙 목록을 반환한다.
    원본 텍스트 기준으로 패턴을 검사한다.
    """
    rules: list[TriggeredRule] = []

    if detected_pii:
        rules.append(TriggeredRule(
            rule_id="PII_DETECTED",
            description=f"개인정보 노출 감지: {', '.join(detected_pii)}",
            min_grade="HIGH",
            category="privacy",
            matched_text=", ".join(detected_pii),
        ))

    m = _THREAT_RE.search(text)
    if m:
        rules.append(TriggeredRule(
            rule_id="DIRECT_THREAT",
            description="직접적 폭력/협박 표현 감지",
            min_grade="HIGH",
            category="threat",
            matched_text=m.group(0),
        ))

    m = _SELF_HARM_RE.search(text)
    if m:
        rules.append(TriggeredRule(
            rule_id="SELF_HARM",
            description="자해 임박 표현 감지",
            min_grade="CRITICAL",
            category="self_harm",
            matched_text=m.group(0),
        ))

    m = _PHISHING_RE.search(text)
    if m:
        rules.append(TriggeredRule(
            rule_id="PHISHING_LINK",
            description="피싱 의심 링크 감지",
            min_grade="HIGH",
            category="policy_violation",
            matched_text=m.group(0)[:80],
        ))

    m = _DOXXING_RE.search(text)
    if m:
        rules.append(TriggeredRule(
            rule_id="DOXXING",
            description="신상털기/개인정보 공개 의심 감지",
            min_grade="HIGH",
            category="privacy",
            matched_text=m.group(0),
        ))

    return rules
