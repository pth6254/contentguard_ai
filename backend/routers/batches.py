"""Preview and queue bounded CSV/XLSX imports without storing the uploaded file."""
import csv
import io
import secrets
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_client_or_operator
from database import get_db
from limiter import limiter
from models import AnalysisJob, BatchImport, Client, Content
from schemas import AnalyzeRequest
from services.rule_detector import mask_pii

router = APIRouter(prefix="/api/batches", tags=["batch-imports"])
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500


async def _read_table(file: UploadFile) -> tuple[str, list[str], list[dict[str, str]]]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(status_code=422, detail="CSV 또는 XLSX 파일을 선택하세요.")
    payload = await file.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="파일은 2MB 이하여야 합니다.")
    try:
        if suffix == ".csv":
            reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig"), newline=""))
            headers = reader.fieldnames or []
            rows = list(reader)
        else:
            from openpyxl import load_workbook
            book = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
            try:
                iterator = book.active.iter_rows(values_only=True)
                headers = [str(value).strip() if value is not None else "" for value in next(iterator)]
                rows = [dict(zip(headers, ["" if value is None else str(value) for value in values]))
                        for values in iterator]
            finally:
                book.close()
    except (UnicodeError, csv.Error, ValueError, StopIteration, OSError, KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=422, detail="파일을 읽을 수 없습니다. UTF-8 CSV 또는 정상적인 XLSX를 확인하세요.") from exc
    if not headers or any(not header for header in headers) or len(set(headers)) != len(headers):
        raise HTTPException(status_code=422, detail="첫 행의 열 이름은 비어 있거나 중복될 수 없습니다.")
    rows = [row for row in rows if any(str(value or "").strip() for value in row.values())]
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail="한 번에 최대 500행까지 접수할 수 있습니다.")
    return suffix[1:], headers, rows


@router.post("/preview")
@limiter.limit("10/hour")
async def preview(request: Request, file: UploadFile = File(...),
                  client: Client | None = Depends(get_client_or_operator)):
    source, headers, rows = await _read_table(file)
    return {"format": source, "columns": headers, "rows": len(rows),
            "sample": [{key: mask_pii(str(value or ""))[0][:100] for key, value in row.items() if key}
                       for row in rows[:5]]}


@router.post("", status_code=202)
@limiter.limit("5/hour")
async def submit(request: Request, file: UploadFile = File(...),
                 content_id_column: str = Form(...), text_column: str = Form(...),
                 client: Client | None = Depends(get_client_or_operator),
                 db: Session = Depends(get_db)):
    source, headers, rows = await _read_table(file)
    if content_id_column not in headers or text_column not in headers or content_id_column == text_column:
        raise HTTPException(status_code=422, detail="서로 다른 콘텐츠 ID 열과 텍스트 열을 선택하세요.")
    client_id = client.id if client else None
    seen = set()
    candidates = []
    errors = []
    for number, row in enumerate(rows, 2):
        try:
            body = AnalyzeRequest(content_id=str(row.get(content_id_column) or "").strip(),
                                  text=str(row.get(text_column) or ""))
        except ValidationError:
            if len(errors) < 25:
                errors.append({"row": number, "reason": "콘텐츠 ID 또는 텍스트 형식이 올바르지 않습니다."})
            continue
        if body.content_id in seen:
            if len(errors) < 25:
                errors.append({"row": number, "reason": "파일 안에서 콘텐츠 ID가 중복되었습니다."})
            continue
        seen.add(body.content_id)
        masked, pii_types = mask_pii(body.text)
        candidates.append((number, body.content_id, masked, pii_types))
    ids = [item[1] for item in candidates]
    existing_contents = {value[0] for value in db.query(Content.content_id).filter(
        Content.client_id == client_id, Content.content_id.in_(ids)).all()} if ids else set()
    keys = [f"client:{client_id if client_id is not None else 'operator'}:{item}" for item in ids]
    existing_keys = {value[0] for value in db.query(AnalysisJob.submission_key).filter(
        AnalysisJob.submission_key.in_(keys)).all()} if keys else set()
    accepted = []
    for number, content_id, masked, pii_types in candidates:
        key = f"client:{client_id if client_id is not None else 'operator'}:{content_id}"
        if content_id in existing_contents or key in existing_keys:
            if len(errors) < 25:
                errors.append({"row": number, "reason": "이미 접수되었거나 분석된 콘텐츠 ID입니다."})
        else:
            accepted.append((content_id, masked, pii_types, key))
    if not accepted:
        raise HTTPException(status_code=422, detail="접수 가능한 행이 없습니다. 열 선택과 중복 ID를 확인하세요.")
    batch = BatchImport(id=secrets.token_hex(16), client_id=client_id, source_format=source,
                        rows_total=len(rows), accepted=len(accepted), skipped=len(rows) - len(accepted))
    db.add(batch)
    db.flush()
    for content_id, masked, pii_types, key in accepted:
        db.add(AnalysisJob(id=secrets.token_hex(16), batch_id=batch.id, client_id=client_id,
                           submission_key=key, content_id=content_id, text=masked, pii_types=pii_types,
                           kind="new", status="PENDING", attempts=0, next_attempt_at=datetime.utcnow()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="다른 요청이 같은 콘텐츠 ID를 먼저 접수했습니다. 다시 미리보기를 실행하세요.")
    return {"id": batch.id, "rows_total": batch.rows_total, "accepted": batch.accepted,
            "skipped": batch.skipped, "errors": errors}


def _batch_result(db: Session, batch: BatchImport) -> dict:
    counts = {status: count for status, count in db.query(AnalysisJob.status, func.count())
              .filter(AnalysisJob.batch_id == batch.id).group_by(AnalysisJob.status).all()}
    return {"id": batch.id, "format": batch.source_format, "rows_total": batch.rows_total,
            "accepted": batch.accepted, "skipped": batch.skipped, "by_status": counts,
            "created_at": batch.created_at}


@router.get("")
def list_batches(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                 client: Client | None = Depends(get_client_or_operator)):
    query = db.query(BatchImport)
    if client:
        query = query.filter(BatchImport.client_id == client.id)
    return [_batch_result(db, batch) for batch in query.order_by(BatchImport.created_at.desc()).limit(limit).all()]


@router.get("/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db),
              client: Client | None = Depends(get_client_or_operator)):
    batch = db.get(BatchImport, batch_id)
    if not batch or (client and batch.client_id != client.id):
        raise HTTPException(status_code=404, detail="접수 내역이 없습니다.")
    return _batch_result(db, batch)
