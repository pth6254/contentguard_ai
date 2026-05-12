import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Demo Client Service")

DB_PATH = "/data/demo.db"
CONTENTGUARD_URL = os.getenv("CONTENTGUARD_URL", "http://backend:8000")
API_KEY = os.getenv("DEMO_CLIENT_API_KEY", "")

ACTION_MESSAGES = {
    "REMOVED":   "🗑️  콘텐츠 삭제 처리 완료",
    "APPROVED":  "✅  콘텐츠 게시 승인",
    "HELD":      "⏸️  콘텐츠 임시 보류",
    "MONITORED": "👁️  콘텐츠 모니터링 등록",
}


# ── DB 초기화 ──────────────────────────────────────────────────────────────

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id    TEXT UNIQUE NOT NULL,
                text          TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'SUBMITTED',
                risk_level    TEXT,
                review_action TEXT,
                reviewed_at   TEXT,
                created_at    TEXT NOT NULL
            )
        """)

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

init_db()


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

class ReviewSubmit(BaseModel):
    text: str


async def _call_contentguard(content_id: str, text: str):
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{CONTENTGUARD_URL}/api/analyze",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"content_id": content_id, "text": text},
            )
            cg_data = resp.json()
        risk_level = cg_data.get("risk_level", "UNKNOWN")
    except Exception as e:
        print(f"[BG] ContentGuard 호출 실패: {e}")
        risk_level = "UNKNOWN"

    with get_db() as conn:
        conn.execute(
            "UPDATE reviews SET status='PENDING', risk_level=? WHERE content_id=?",
            (risk_level, content_id),
        )
    print(f"[BG] content_id={content_id} risk_level={risk_level}")


@app.post("/reviews", status_code=201)
async def submit_review(body: ReviewSubmit, background_tasks: BackgroundTasks):
    """
    1. 데모 DB에 리뷰 저장 후 즉시 응답
    2. 백그라운드에서 ContentGuard API 분석 요청
    3. 분석 완료 시 DB risk_level 업데이트 → PENDING 상태로 전환
    """
    content_id = f"demo-{int(time.time())}"
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with get_db() as conn:
        conn.execute(
            "INSERT INTO reviews (content_id, text, status, created_at) VALUES (?, ?, 'SUBMITTED', ?)",
            (content_id, body.text, created_at),
        )

    background_tasks.add_task(_call_contentguard, content_id, body.text)
    print(f"[SUBMIT] content_id={content_id} → ContentGuard 분석 백그라운드 시작")
    return {"content_id": content_id, "status": "SUBMITTED"}


@app.post("/webhook")
async def receive_webhook(request: Request):
    """ContentGuard 심사 완료 시 호출 → 데모 DB 상태 업데이트"""
    payload = await request.json()
    content_id    = payload.get("content_id")
    review_status = payload.get("review_status")
    review_action = payload.get("review_action")
    reviewed_at   = payload.get("reviewed_at")

    with get_db() as conn:
        conn.execute(
            "UPDATE reviews SET status=?, review_action=?, reviewed_at=? WHERE content_id=?",
            (review_status, review_action, reviewed_at, content_id),
        )

    action_msg = ACTION_MESSAGES.get(review_status, f"상태 처리: {review_status}")
    print(f"[WEBHOOK] {action_msg} — content_id={content_id}")
    return {"ok": True, "action_taken": action_msg}


@app.get("/reviews")
def list_reviews():
    """데모 DB의 전체 리뷰 목록 (최신순 20건)"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/reviews/{content_id}")
def get_review(content_id: str):
    """특정 리뷰의 현재 상태 조회"""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE content_id=?", (content_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return dict(row)


@app.get("/health")
def health():
    return {"status": "ok"}
