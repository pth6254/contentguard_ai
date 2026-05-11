import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from routers import active_learning, admin, analyze, contents, crawl, register, reviews, upload
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Secret"],
    expose_headers=["X-Total-Count"],
)

app.include_router(auth_router.router)
app.include_router(register.router)
app.include_router(analyze.router)
app.include_router(contents.router)
app.include_router(reviews.router)
app.include_router(active_learning.router)
app.include_router(upload.router)
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
                "초기 운영자 생성: email=%s", settings.OPERATOR_EMAIL
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
        checks["db"] = f"error: {e}"

    try:
        client = ollama_lib.Client(host=settings.OLLAMA_BASE_URL)
        client.list()
        checks["ollama"] = "ok"
    except Exception as e:
        checks["ollama"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}
