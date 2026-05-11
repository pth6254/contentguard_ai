import io
import json
import logging
import time
from typing import Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from database import get_db, SessionLocal
from limiter import limiter
from models import Client, Content
from schemas import UploadResult, UploadError
from services.content_service import save_analysis
from services.llm_service import generate_explanation
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

MAX_ROWS = 1000
SUPPORTED = {".csv", ".xlsx", ".xls", ".json", ".txt"}

# HIGH/CRITICAL은 즉시 LLM 설명 생성, MEDIUM/LOW는 백그라운드 처리
_IMMEDIATE_LEVELS = {"HIGH", "CRITICAL"}


# ── 형식별 파서 ────────────────────────────────────────────────────────────

def _cell(value) -> str:
    """pandas NaN을 빈 문자열로 변환."""
    return "" if pd.isna(value) else str(value).strip()


def _extract_rows(df: pd.DataFrame, prefix: str) -> list[tuple[str, str]]:
    if "text" not in df.columns:
        raise ValueError("필수 컬럼 'text'가 없습니다. 필요한 컬럼: text, content_id(선택)")
    if "content_id" in df.columns:
        return [(_cell(r["content_id"]), _cell(r["text"])) for _, r in df.iterrows()]
    return [(f"{prefix}_{i+1:04d}", _cell(r["text"])) for i, (_, r) in enumerate(df.iterrows())]


def _parse_csv(raw: bytes) -> list[tuple[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("UTF-8 인코딩 파일만 지원합니다.")
    df = pd.read_csv(io.StringIO(text))
    return _extract_rows(df, f"CSV_{int(time.time())}")


def _parse_excel(raw: bytes) -> list[tuple[str, str]]:
    df = pd.read_excel(io.BytesIO(raw))
    return _extract_rows(df, f"XLS_{int(time.time())}")


def _parse_json(raw: bytes) -> list[tuple[str, str]]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"JSON 파싱 실패: {e}")
    if not isinstance(data, list):
        raise ValueError("JSON 최상위가 배열이어야 합니다. 예: [{\"content_id\": \"...\", \"text\": \"...\"}]")
    rows = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "content_id" not in item or "text" not in item:
            raise ValueError(f"항목 {i}: 'content_id'와 'text' 키가 필요합니다.")
        rows.append((str(item["content_id"]).strip(), str(item["text"]).strip()))
    return rows


def _parse_txt(raw: bytes) -> list[tuple[str, str]]:
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        raise ValueError("UTF-8 인코딩 파일만 지원합니다.")
    prefix = f"TXT_{int(time.time())}"
    rows = []
    for i, line in enumerate(lines, start=1):
        text = line.strip()
        if text:
            rows.append((f"{prefix}_{i:04d}", text))
    return rows


PARSERS = {
    ".csv":  _parse_csv,
    ".xlsx": _parse_excel,
    ".xls":  _parse_excel,
    ".json": _parse_json,
    ".txt":  _parse_txt,
}


# ── 백그라운드 LLM 설명 생성 ────────────────────────────────────────────────

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


# ── 공통 저장 로직 ─────────────────────────────────────────────────────────

def _save_rows(
    rows: list[tuple[str, str]],
    client_id: Optional[int],
    db: Session,
    background_tasks: BackgroundTasks,
) -> UploadResult:
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"최대 {MAX_ROWS}건까지 업로드 가능합니다.")

    saved = skipped = 0
    errors: list[UploadError] = []

    for i, (content_id, text_val) in enumerate(rows, start=1):
        if not content_id or not text_val:
            errors.append(UploadError(row=i, content_id=content_id, reason="content_id 또는 text가 비어있습니다."))
            continue

        if db.query(Content).filter(Content.content_id == content_id).first():
            skipped += 1
            continue

        try:
            all_predictions = prediction_service.predict_all(text_val)
            final = prediction_service.get_final_result(all_predictions)

            # HIGH/CRITICAL: 즉시 LLM 설명 생성 (운영자 심사가 시급)
            explanation = None
            if final["risk_level"] in _IMMEDIATE_LEVELS:
                explanation = generate_explanation(
                    text=text_val,
                    risk_score=final["risk_score"],
                    risk_level=final["risk_level"],
                    recommended_action=final["recommended_action"],
                )

            save_analysis(db, content_id, text_val, client_id, all_predictions, final, explanation)
            saved += 1

            # MEDIUM/LOW: 응답 후 백그라운드에서 LLM 설명 생성
            if final["risk_level"] not in _IMMEDIATE_LEVELS:
                background_tasks.add_task(
                    _generate_and_save_explanation,
                    content_id, text_val, final["risk_score"], final["risk_level"], final["recommended_action"],
                )

        except Exception as e:
            errors.append(UploadError(row=i, content_id=content_id, reason=str(e)))

    return UploadResult(total=len(rows), saved=saved, skipped=skipped, errors=errors)


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResult)
@limiter.limit("20/hour")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: Optional[Client] = Depends(get_client_or_operator),
):
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다. 지원 형식: {', '.join(SUPPORTED)}",
        )

    raw = await file.read()
    try:
        rows = PARSERS[ext](raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = _save_rows(rows, client.id if client else None, db, background_tasks)
    logger.info(
        "파일 업로드: filename=%s total=%d saved=%d skipped=%d errors=%d",
        filename, result.total, result.saved, result.skipped, len(result.errors),
    )
    return result
