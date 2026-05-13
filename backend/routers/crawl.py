import json
import logging
import time
from typing import Generator, Optional

import requests as http
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from config import settings
from database import get_db
from limiter import limiter
from models import Client
from schemas import CrawlRequest
from services.category_scorer import compute_category_scores
from services.content_service import save_analysis
from services.decision_policy_service import apply_forced_escalation
from services.evidence_service import extract_evidence_spans
from services.llm_service import extract_texts, classify_and_explain
from services.rule_detector import mask_pii, detect_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["crawl"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _scrape(url: str) -> tuple[str, str]:
    """(markdown, html) 반환."""
    resp = http.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers={"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown", "html"]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl 오류: {data}")
    return data["data"]["markdown"], data["data"].get("html", "")


def _stream(
    url: str,
    max_items: int,
    db: Session,
    client_id: Optional[int],
) -> Generator[str, None, None]:
    if not settings.FIRECRAWL_API_KEY:
        yield _sse({"type": "error", "message": "FIRECRAWL_API_KEY가 설정되지 않았습니다."})
        return

    # 1단계: 스크래핑
    yield _sse({"type": "status", "message": "페이지 스크래핑 중..."})
    try:
        markdown, html = _scrape(url)
    except Exception as e:
        yield _sse({"type": "error", "message": f"스크래핑 실패: {e}"})
        return
    yield _sse({"type": "scraped", "chars": len(markdown)})

    # 2단계: 하이브리드 텍스트 추출 (Trafilatura 우선, 품질 미달 시 LLM 폴백)
    yield _sse({"type": "status", "message": "텍스트 추출 중..."})
    try:
        texts, method = extract_texts(html, markdown, max_items)
    except Exception as e:
        yield _sse({"type": "error", "message": f"텍스트 추출 실패: {e}"})
        return
    yield _sse({"type": "extracted", "count": len(texts), "method": method})

    if not texts:
        yield _sse({"type": "done", "saved": 0, "skipped": 0, "errors": 0})
        return

    # 3단계: 항목별 LLM 분류 및 저장
    saved = skipped = errors = 0
    prefix = f"CRAWL_{int(time.time())}"

    for i, text in enumerate(texts, start=1):
        content_id = f"{prefix}_{i:03d}"
        try:
            masked_text, detected_pii = mask_pii(text)
            category_hints = compute_category_scores(text)
            triggered_rules_obj = detect_rules(text, detected_pii)
            triggered_rules = [r.to_dict() for r in triggered_rules_obj]

            # LLM 분류 + 설명 (1회 호출, NO_THINK 상시 활성)
            llm_result = classify_and_explain(masked_text, category_hints, triggered_rules)
            category_scores = llm_result["category_scores"]

            final_score, final_grade, final_action = apply_forced_escalation(
                llm_result["risk_score"], triggered_rules_obj
            )
            final = {
                "risk_score": final_score,
                "risk_level": final_grade,
                "recommended_action": final_action,
            }

            evidence_spans = extract_evidence_spans(masked_text, category_scores)

            # HIGH/CRITICAL 심층 분석 (LLM_DEEP_ANALYSIS=true 시 활성)
            deep_analysis = None
            if settings.LLM_DEEP_ANALYSIS and final_grade in ("HIGH", "CRITICAL"):
                from services.deep_analysis import analyze_deeply
                deep_analysis = analyze_deeply(
                    text, final_grade, category_scores, triggered_rules, evidence_spans
                )

            explanation_json = {
                "summary":                    llm_result.get("summary", ""),
                "score_explanation":          llm_result.get("score_explanation", ""),
                "main_reasons":               llm_result.get("main_reasons", []),
                "evidence":                   llm_result.get("evidence", []),
                "recommended_operator_check": llm_result.get("recommended_operator_check", ""),
                "confidence_note":            llm_result.get("confidence_note", ""),
            }
            if deep_analysis:
                explanation_json["deep_analysis"] = deep_analysis

            record = save_analysis(
                db, content_id, text, client_id, [], final,
                explanation=explanation_json.get("summary", ""),
                category_scores=category_scores,
                triggered_rules=triggered_rules,
                evidence_spans=evidence_spans,
                explanation_json=explanation_json,
                calibrated_score=llm_result["risk_score"],
            )
            saved += 1

            yield _sse({
                "type": "item",
                "content_id": content_id,
                "text": text,
                "risk_level": record.risk_level,
                "risk_score": record.risk_score,
                "triggered_rules": len(triggered_rules),
            })
        except Exception as e:
            errors += 1
            logger.error("크롤링 항목 분석 실패: content_id=%s error=%s", content_id, e)
            yield _sse({"type": "item_error", "text": text[:40], "reason": str(e)})

    logger.info("크롤링 완료: url=%s saved=%d skipped=%d errors=%d", url, saved, skipped, errors)
    yield _sse({"type": "done", "saved": saved, "skipped": skipped, "errors": errors})


@router.post("/crawl")
@limiter.limit("10/hour")
def crawl(
    request: Request,
    body: CrawlRequest,
    db: Session = Depends(get_db),
    client: Optional[Client] = Depends(get_client_or_operator),
):
    return StreamingResponse(
        _stream(body.url, body.max_items, db, client.id if client else None),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
