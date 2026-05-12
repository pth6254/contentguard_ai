from collections import deque
from datetime import datetime

from fastapi import FastAPI, Request

app = FastAPI(title="Demo Webhook Receiver")

# 최근 100건만 메모리에 보관
_logs: deque = deque(maxlen=100)

ACTION_MESSAGES = {
    "REMOVED":    "🗑️  콘텐츠 삭제 처리 완료",
    "APPROVED":   "✅  콘텐츠 게시 승인",
    "HELD":       "⏸️  콘텐츠 임시 보류",
    "MONITORED":  "👁️  콘텐츠 모니터링 등록",
}


@app.post("/webhook")
async def receive_webhook(request: Request):
    payload = await request.json()
    status = payload.get("review_status", "UNKNOWN")
    entry = {
        "received_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
        "action_taken": ACTION_MESSAGES.get(status, f"상태 처리: {status}"),
    }
    _logs.appendleft(entry)
    print(f"[WEBHOOK] {entry['action_taken']} — content_id={payload.get('content_id')}")
    return {"ok": True, "action_taken": entry["action_taken"]}


@app.get("/logs")
def get_logs():
    return list(_logs)


@app.get("/health")
def health():
    return {"status": "ok"}
