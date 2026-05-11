import json
import logging
import time
from typing import Generator, Optional

import requests as http
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from config import settings
from database import get_db, SessionLocal
from limiter import limiter
from models import Client, Content
from schemas import CrawlRequest
from services.content_service import save_analysis
from services.llm_service import extract_texts, generate_explanation
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["crawl"])

# HIGH/CRITICAL은 스트리밍 중 즉시 생성, MEDIUM/LOW는 스트림 완료 후 백그라운드 처리
_IMMEDIATE_LEVELS = {"HIGH", "CRITICAL"}


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


def _generate_and_save_explanation(
    content_id: str, text: str, risk_score: float, risk_level: str, recommended_action: str
) -> None:
    """MEDIUM/LOW 항목의 LLM 설명을 백그라운드에서 생성하고 저장한다."""
    db = SessionLocal()
    try:
        explanation = generate_explanation(
            text=text, risk_score=risk_score, risk_level=risk_level, recommended_action=recommended_action,
        )
        record = db.query(Content).filter(Content.content_id == content_id).first()
        if record and record.explanation is None:
            record.explanation = explanation
            db.commit()
            logger.info("백그라운드 설명 저장 완료: content_id=%s", content_id)
    except Exception as e:
        logger.error("백그라운드 설명 생성 실패: content_id=%s error=%s", content_id, e)
    finally:
        db.close()


def _stream(
    url: str,
    max_items: int,
    db: Session,
    client_id: Optional[int],
    background_tasks: BackgroundTasks,
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

    # 3단계: 항목별 분석 및 저장
    saved = skipped = errors = 0
    prefix = f"CRAWL_{int(time.time())}"

    for i, text in enumerate(texts, start=1):
        content_id = f"{prefix}_{i:03d}"
        try:
            all_predictions = prediction_service.predict_all(text)
            final = prediction_service.get_final_result(all_predictions)

            # HIGH/CRITICAL: 즉시 LLM 설명 생성 (운영자 심사가 시급)
            explanation = None
            if final["risk_level"] in _IMMEDIATE_LEVELS:
                explanation = generate_explanation(
                    text=text,
                    risk_score=final["risk_score"],
                    risk_level=final["risk_level"],
                    recommended_action=final["recommended_action"],
                )

            record = save_analysis(db, content_id, text, client_id, all_predictions, final, explanation)
            saved += 1

            # MEDIUM/LOW: 스트림 완료 후 백그라운드에서 LLM 설명 생성
            if final["risk_level"] not in _IMMEDIATE_LEVELS:
                background_tasks.add_task(
                    _generate_and_save_explanation,
                    content_id, text, final["risk_score"], final["risk_level"], final["recommended_action"],
                )

            yield _sse({
                "type": "item",
                "content_id": content_id,
                "text": text,
                "risk_level": record.risk_level,
                "risk_score": record.risk_score,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    client: Optional[Client] = Depends(get_client_or_operator),
):
    return StreamingResponse(
        _stream(body.url, body.max_items, db, client.id if client else None, background_tasks),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
