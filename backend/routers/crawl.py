import json
import logging
import time
from typing import Generator, Optional

import ollama as ollama_lib
import requests as http
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from config import settings
from database import get_db
from limiter import limiter
from models import Client, Content, ModelPrediction
from schemas import CrawlRequest
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


def _extract_texts(markdown: str, max_items: int) -> list[str]:
    client = ollama_lib.Client(host=settings.OLLAMA_BASE_URL)
    prompt = f"""다음은 웹페이지를 마크다운으로 변환한 내용입니다.
사용자가 직접 작성한 댓글, 리뷰, 게시글 본문만 추출하세요.
메뉴, 광고, 버튼, 날짜, 작성자명 등 부가 정보는 제외하세요.
최대 {max_items}개를 JSON 문자열 배열로만 반환하세요. 설명 없이 배열만 출력하세요.

출력 형식:
["텍스트1", "텍스트2", "텍스트3"]

마크다운:
{markdown[:6000]}"""

    response = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )
    content = response["message"]["content"].strip()
    start = content.find("[")
    end   = content.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("JSON 배열을 찾을 수 없습니다.")
    return json.loads(content[start:end])


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

    # 2단계: Ollama 텍스트 추출
    yield _sse({"type": "status", "message": f"텍스트 추출 중 (Ollama {settings.OLLAMA_MODEL})..."})
    try:
        texts = _extract_texts(markdown, max_items)
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
            if db.query(Content).filter(Content.content_id == content_id).first():
                skipped += 1
                continue

            all_predictions = prediction_service.predict_all(text)
            final = prediction_service.get_final_result(all_predictions)

            record = Content(
                client_id=client_id,
                content_id=content_id,
                text=text,
                risk_score=final["risk_score"],
                risk_level=final["risk_level"],
                recommended_action=final["recommended_action"],
                explanation=None,
            )
            db.add(record)
            db.flush()

            for pred in all_predictions:
                db.add(ModelPrediction(
                    content_id=content_id,
                    model_name=pred["model_name"],
                    model_version=pred["model_version"],
                    model_type=pred["model_type"],
                    risk_score=pred["risk_score"],
                    risk_level=pred["risk_level"],
                    recommended_action=pred["recommended_action"],
                    confidence=pred.get("confidence"),
                    latency_ms=pred.get("latency_ms"),
                    is_selected=pred["is_selected"],
                    is_shadow=pred["is_shadow"],
                ))

            db.commit()
            saved += 1

            yield _sse({
                "type": "item",
                "content_id": content_id,
                "text": text,
                "risk_level": final["risk_level"],
                "risk_score": final["risk_score"],
            })

        except Exception as e:
            db.rollback()
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
