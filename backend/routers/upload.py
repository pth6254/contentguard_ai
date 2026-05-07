import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models import Content, ModelPrediction
from schemas import UploadResult, UploadError
from services.prediction_service import prediction_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

MAX_ROWS = 1000


@router.post("/upload/csv", response_model=UploadResult)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (file.filename or "").endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="UTF-8 인코딩 파일만 지원합니다.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "content_id" not in reader.fieldnames or "text" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV에 'content_id'와 'text' 컬럼이 필요합니다.")

    rows = list(reader)
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"최대 {MAX_ROWS}건까지 업로드 가능합니다.")

    saved = skipped = 0
    errors: list[UploadError] = []

    for i, row in enumerate(rows, start=2):
        content_id = (row.get("content_id") or "").strip()
        text_val   = (row.get("text") or "").strip()

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

    logger.info("CSV upload: total=%d saved=%d skipped=%d errors=%d", len(rows), saved, skipped, len(errors))
    return UploadResult(total=len(rows), saved=saved, skipped=skipped, errors=errors)
