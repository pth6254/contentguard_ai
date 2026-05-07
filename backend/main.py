import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routers import active_learning, admin, analyze, contents, crawl, reviews, upload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ContentGuard AI",
    description="AI 기반 콘텐츠 리스크 분석 API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(contents.router)
app.include_router(reviews.router)
app.include_router(active_learning.router)
app.include_router(upload.router)
app.include_router(crawl.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
