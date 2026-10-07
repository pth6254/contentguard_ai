import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from routers import active_learning, admin, analyze, batches, client_portal, contents, crawl, evaluations, jobs, operations, policies, register, reviews
from routers import auth as auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="ContentGuard AI",
    description="AI 기반 콘텐츠 리스크 분석 API",
    version="0.3.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Secret"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth_router.router)
app.include_router(client_portal.router)
app.include_router(batches.router)
app.include_router(register.router)
app.include_router(analyze.router)
app.include_router(contents.router)
app.include_router(reviews.router)
app.include_router(active_learning.router)
app.include_router(evaluations.router)
app.include_router(jobs.router)
app.include_router(operations.router)
app.include_router(policies.router)
app.include_router(crawl.router)
app.include_router(admin.router)


@app.on_event("startup")
def seed_initial_operator() -> None:
    """OPERATOR_EMAIL/OPERATOR_PASSWORD가 설정되어 있고 operators 테이블이 비어 있으면 초기 운영자를 생성한다."""
    if not settings.OPERATOR_EMAIL or not settings.OPERATOR_PASSWORD:
        return
    from auth import hash_password
    from database import SessionLocal
    from models import Operator
    db = SessionLocal()
    try:
        if db.query(Operator).count() == 0:
            op = Operator(
                email=settings.OPERATOR_EMAIL,
                password_hash=hash_password(settings.OPERATOR_PASSWORD),
                name="관리자",
            )
            db.add(op)
            db.commit()
            logging.getLogger(__name__).info(
                "초기 운영자 생성: id=%s", op.id
            )
    finally:
        db.close()


@app.get("/health")
def health_check():
    from sqlalchemy import text
    from database import engine
    from config import settings
    import ollama as ollama_lib

    checks = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = "error"

    try:
        if "ollama" in (settings.LLM_PROVIDER_EXPLAIN, settings.LLM_PROVIDER_EXTRACT):
            client = ollama_lib.Client(host=settings.OLLAMA_BASE_URL, timeout=3.0)
            client.list()
            checks["ollama"] = "ok"
        else:
            checks["ollama"] = "not_required"
    except Exception as e:
        checks["ollama"] = "error"

    try:
        from database import SessionLocal
        with SessionLocal() as db:
            checks.update({f"{kind}_worker": status for kind, status in operations.worker_status(db).items()})
    except Exception:
        checks.update(analysis_worker="unknown", webhook_worker="unknown")
    overall = "ok" if all(v in ("ok", "not_required") for v in checks.values()) else "degraded"
    return {"status": overall, **checks}


@app.get("/ready")
def readiness():
    from sqlalchemy import text
    from database import engine
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}
