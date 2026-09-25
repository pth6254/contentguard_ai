from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Content


def find_content(db: Session, content_id: str, record_id: int | None = None, lock: bool = False) -> Content:
    query = db.query(Content).filter(Content.content_id == content_id)
    if record_id is not None:
        query = query.filter(Content.id == record_id)
    if lock:
        query = query.with_for_update()
    records = query.limit(2).all()
    if not records:
        raise HTTPException(status_code=404, detail=f"content_id '{content_id}' 를 찾을 수 없습니다.")
    if len(records) > 1:
        raise HTTPException(status_code=409, detail="여러 고객의 콘텐츠 ID가 같습니다. record_id를 지정하세요.")
    return records[0]
