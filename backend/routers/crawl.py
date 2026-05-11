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
from services.content_service import save_analysis
from services.llm_service import extract_texts, generate_explanation
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["crawl"])


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _scrape(url: str) -> str:
    resp = http.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers={"Authorization": f"Bearer {settings.FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown"]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl 오류: {data}")
    return data["data"]["markdown"]




def _stream(url: str, max_items: int, db: Session, client_id: Optional[int]) -> Generator[str, None, None]:
    if not settings.FIRECRAWL_API_KEY:
        yield _sse({"type": "error", "message": "FIRECRAWL_API_KEY가 설정되지 않았습니다."})
        return

    # 1단계: 스크래핑
    yield _sse({"type": "status", "message": "페이지 스크래핑 중..."})
    try:
        markdown = _scrape(url)
    except Exception as e:
        yield _sse({"type": "error", "message": f"스크래핑 실패: {e}"})
        return
    yield _sse({"type": "scraped", "chars": len(markdown)})

    # 2단계: LLM 텍스트 추출
    yield _sse({"type": "status", "message": f"텍스트 추출 중 ({settings.LLM_PROVIDER_EXTRACT})..."})
    try:
        texts = extract_texts(markdown, max_items)
    except Exception as e:
        yield _sse({"type": "error", "message": f"텍스트 추출 실패: {e}"})
        return
    yield _sse({"type": "extracted", "count": len(texts)})

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
            explanation = generate_explanation(
                text=text,
                risk_score=final["risk_score"],
                risk_level=final["risk_level"],
                recommended_action=final["recommended_action"],
            )
            record = save_analysis(db, content_id, text, client_id, all_predictions, final, explanation)
            saved += 1
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
    db: Session = Depends(get_db),
    client: Optional[Client] = Depends(get_client_or_operator),
):
    return StreamingResponse(
        _stream(body.url, body.max_items, db, client.id if client else None),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
