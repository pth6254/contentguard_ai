import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from routers import active_learning, admin, analyze, contents, crawl, register, reviews, upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

app = FastAPI(
    title="ContentGuard AI",
    description="AI 기반 콘텐츠 리스크 분석 API",
    version="0.2.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(register.router)
app.include_router(analyze.router)
app.include_router(contents.router)
app.include_router(reviews.router)
app.include_router(active_learning.router)
app.include_router(upload.router)
app.include_router(crawl.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    from sqlalchemy import text
    from database import engine
    from config import settings
    import ollama as ollama_lib

    checks = {}

    # DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"

    # Ollama
    try:
        client = ollama_lib.Client(host=settings.OLLAMA_BASE_URL)
        client.list()
        checks["ollama"] = "ok"
    except Exception as e:
        checks["ollama"] = f"error: {e}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, **checks}
