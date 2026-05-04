# ContentGuard AI

AI 기반 콘텐츠 위험도 분석 및 운영자 심사 시스템

## 개요

ContentGuard AI는 텍스트 콘텐츠의 위험도를 자동으로 분석하고, 운영자가 최종 판단을 내릴 수 있도록 지원하는 Human-in-the-loop 콘텐츠 모더레이션 시스템입니다.

**핵심 철학: AI가 판단하고, LLM이 설명하고, 사람이 결정한다.**

## 주요 기능

- **ML 위험도 분석**: TF-IDF + Ridge Regression으로 텍스트 위험 점수(0.0~1.0) 산출
- **LLM 설명 생성**: Ollama(qwen3.5:9b)로 위험 판단 근거를 한국어로 설명
- **운영자 심사 시스템**: PENDING → 승인/삭제/보류/모니터링 워크플로우
- **Streamlit 대시보드**: 통계, 심사 큐, 분석, 이력 관리 UI

## 아키텍처

```
contentguard_ai/
├── backend/                  # FastAPI 백엔드
│   ├── main.py               # 앱 진입점
│   ├── config.py             # 환경변수 설정
│   ├── database.py           # SQLAlchemy DB 연결
│   ├── models.py             # ORM 모델 (Contents 테이블)
│   ├── schemas.py            # Pydantic 요청/응답 스키마
│   ├── routers/
│   │   ├── analyze.py        # POST /api/analyze
│   │   ├── contents.py       # GET /api/contents
│   │   └── reviews.py        # POST /api/reviews/{id}
│   └── services/
│       ├── prediction_service.py  # ML 위험도 예측
│       ├── llm_service.py         # Ollama LLM 설명 생성
│       └── risk_service.py        # 규칙 기반 스코어링 (보조)
├── dashboard/                # Streamlit 프론트엔드
│   ├── app.py                # 대시보드 UI (4개 페이지)
│   └── api_client.py         # FastAPI HTTP 클라이언트
├── data/
│   └── training_data.csv     # ML 학습 데이터 500건
├── models/                   # 학습된 모델 파일
│   ├── tfidf_vectorizer.pkl
│   └── ridge_model.pkl
├── scripts/
│   └── train.py              # ML 모델 학습 스크립트
├── .env                      # 환경변수 (로컬용, git 제외)
├── .env.example              # 환경변수 템플릿
├── docker-compose.yml        # PostgreSQL 17 컨테이너
└── requirements.txt          # Python 패키지 목록
```

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | FastAPI, Uvicorn |
| 데이터베이스 | PostgreSQL 17 (Docker), SQLAlchemy ORM |
| ML 모델 | scikit-learn (TF-IDF + Ridge Regression) |
| LLM | Ollama (qwen3.5:9b), 로컬 실행 |
| 프론트엔드 | Streamlit |
| 인프라 | Docker Compose |

## 위험 등급 기준

| 등급 | 점수 범위 | 권장 조치 |
|------|-----------|-----------|
| 🟢 LOW | 0.00 ~ 0.29 | approve (자동 승인) |
| 🟡 MEDIUM | 0.30 ~ 0.59 | monitor (모니터링) |
| 🔴 HIGH | 0.60 ~ 0.84 | hold (보류 후 심사) |
| 🚨 CRITICAL | 0.85 ~ 1.00 | remove (즉시 삭제) |

## 콘텐츠 상태 흐름

```
분석 요청
    │
    ▼
PENDING (AI 분석 완료, 심사 대기)
    │
    ├── 승인 → APPROVED
    ├── 삭제 → REMOVED
    ├── 보류 → HELD
    └── 모니터링 → MONITORED
```

## 시작하기

### 사전 요구사항

- Python 3.10+
- Docker Desktop
- Ollama (Windows에서 실행, qwen3.5:9b 모델 필요)
- WSL2 (백엔드 실행 환경)

### 1. 환경변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 DATABASE_URL, OLLAMA_BASE_URL 등 설정
```

`.env` 예시:
```
DATABASE_URL=postgresql+psycopg2://contentguard:contentguard@localhost:5434/contentguard_db
OLLAMA_BASE_URL=http://172.18.144.1:11434
OLLAMA_MODEL=qwen3.5:9b
```

> WSL에서 Windows Ollama에 접근할 때는 `ip route | grep default`로 게이트웨이 IP를 확인하여 OLLAMA_BASE_URL에 사용하세요.

### 2. 패키지 설치

```bash
python -m venv venv
source venv/bin/activate  # WSL
pip install -r requirements.txt
```

### 3. PostgreSQL 실행

```bash
# PowerShell (Windows)
docker compose up -d
```

### 4. ML 모델 학습

```bash
# WSL
python scripts/train.py
```

### 5. 백엔드 실행

```bash
# WSL
cd backend
uvicorn main:app --reload --port 8000
```

API 문서: http://localhost:8000/docs

### 6. Ollama 실행

```bash
# PowerShell (Windows)
ollama serve
```

### 7. 대시보드 실행

```bash
# WSL (별도 터미널)
cd dashboard
streamlit run app.py
```

대시보드: http://localhost:8501

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/api/analyze` | 콘텐츠 위험도 분석 |
| GET | `/api/contents` | 콘텐츠 목록 조회 (status 필터 가능) |
| GET | `/api/contents/{id}` | 콘텐츠 단건 조회 |
| POST | `/api/reviews/{id}` | 운영자 심사 결과 제출 |

### 분석 요청 예시

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"content_id": "C001", "text": "분석할 텍스트 내용"}'
```

### 심사 제출 예시

```bash
curl -X POST http://localhost:8000/api/reviews/C001 \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "comment": "문제 없음"}'
```

## ML 모델 성능

학습 데이터 500건 기준:

| 지표 | 값 |
|------|-----|
| MAE | 0.1337 |
| R² | 0.8081 |
| 등급 정확도 | 62% |

- **특징 추출**: TF-IDF (char_wb, n-gram 2~4, max_features 15,000)
- **모델**: Ridge Regression (회귀 → 점수 → 등급 분류)
- **학습 데이터**: 텍스트 + 점수(0.0~1.0) 형식의 500건

## 대시보드 페이지

| 페이지 | 기능 |
|--------|------|
| 대시보드 | 전체 통계, 위험 등급 분포 차트, 최근 분석 내역 |
| 심사 큐 | PENDING 콘텐츠 목록, 승인/삭제/보류/모니터링 버튼 |
| 콘텐츠 분석 | 텍스트 직접 입력 후 즉시 AI 분석 |
| 전체 이력 | 상태별 필터링, AI 설명 및 운영자 메모 조회 |
