"""
위험 근거 스팬(evidence span) 추출 서비스.
마스킹된 텍스트에서 상위 카테고리 키워드의 위치를 찾아 반환한다.
개인정보가 마스킹된 텍스트를 기준으로 하므로 PII가 노출되지 않는다.
"""
import logging
from services.category_scorer import KEYWORDS

logger = logging.getLogger(__name__)

_SEVERITY_THRESHOLDS = [
    (80, "critical"),
    (60, "high"),
    (40, "medium"),
    (0,  "low"),
]


def _to_severity(score_0_100: int) -> str:
    for threshold, sev in _SEVERITY_THRESHOLDS:
        if score_0_100 >= threshold:
            return sev
    return "low"


def extract_evidence_spans(
    masked_text: str,
    category_scores: dict[str, int],
    max_spans: int = 5,
) -> list[dict]:
    """
    카테고리 점수 상위 순으로 키워드를 탐색해 evidence_span 목록을 반환한다.

    반환 형식:
    [{"text": "...", "category": "threat", "severity": "high",
      "start_index": 5, "end_index": 13}, ...]
    """
    sorted_cats = sorted(
        category_scores.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )
    spans: list[dict] = []
    seen_positions: set[tuple[int, int]] = set()

    for cat, score in sorted_cats:
        if score == 0:
            continue
        for kw, weight in KEYWORDS.get(cat, []):
            start = masked_text.find(kw)
            if start == -1:
                continue
            end = start + len(kw)
            pos = (start, end)
            if pos in seen_positions:
                continue
            seen_positions.add(pos)
            spans.append({
                "text": kw,
                "category": cat,
                "severity": _to_severity(round(weight * 100)),
                "start_index": start,
                "end_index": end,
            })
            if len(spans) >= max_spans:
                return spans

    return spans
