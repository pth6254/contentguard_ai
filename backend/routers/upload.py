import io
import json
import logging
import time

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from auth import get_client
from database import get_db
from models import Client, Content, ModelPrediction
from schemas import UploadResult, UploadError
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

MAX_ROWS = 1000
SUPPORTED = {".csv", ".xlsx", ".xls", ".json", ".txt"}


# ── 형식별 파서 ────────────────────────────────────────────────────────────

def _parse_csv(raw: bytes) -> list[tuple[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("UTF-8 인코딩 파일만 지원합니다.")
    df = pd.read_csv(io.StringIO(text))
    if "content_id" not in df.columns or "text" not in df.columns:
        raise ValueError("'content_id'와 'text' 컬럼이 필요합니다.")
    return [(str(r["content_id"]).strip(), str(r["text"]).strip()) for _, r in df.iterrows()]


def _parse_excel(raw: bytes) -> list[tuple[str, str]]:
    df = pd.read_excel(io.BytesIO(raw))
    if "content_id" not in df.columns or "text" not in df.columns:
        raise ValueError("'content_id'와 'text' 컬럼이 필요합니다.")
    return [(str(r["content_id"]).strip(), str(r["text"]).strip()) for _, r in df.iterrows()]


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


# ── 공통 저장 로직 ─────────────────────────────────────────────────────────

def _save_rows(
    rows: list[tuple[str, str]],
    client_id: int,
    db: Session,
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

            record = Content(
                client_id=client_id,
                content_id=content_id,
                text=text_val,
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
        except Exception as e:
            db.rollback()
            errors.append(UploadError(row=i, content_id=content_id, reason=str(e)))

    return UploadResult(total=len(rows), saved=saved, skipped=skipped, errors=errors)


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResult)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: Client = Depends(get_client),
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

    result = _save_rows(rows, client.id, db)
    logger.info(
        "파일 업로드: filename=%s total=%d saved=%d skipped=%d errors=%d",
        filename, result.total, result.saved, result.skipped, len(result.errors),
    )
    return result
