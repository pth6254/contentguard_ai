# ContentGuard AI

AI 기반 콘텐츠 위험도 분석 및 운영자 심사 시스템

## 개요

ContentGuard AI는 텍스트 콘텐츠의 위험도를 자동으로 분석하고, 운영자가 최종 판단을 내릴 수 있도록 지원하는 Human-in-the-loop 콘텐츠 모더레이션 시스템입니다.

**핵심 철학: AI가 판단하고, LLM이 설명하고, 사람이 결정한다.**

## 주요 기능

- **다중 ML 모델**: Ridge Regression / Linear SVM / Logistic Regression 동시 실행 및 결과 저장
- **모델 플러그인 구조**: `BaseMLModel` 인터페이스로 새 모델을 코드 최소 변경으로 추가 가능
- **Shadow Mode**: primary 모델 외 나머지 모델은 shadow 실행 — 결과에 영향 없이 비교 데이터 축적
- **Decision Policy**: `primary_only` / `conservative` / `ensemble_mean` / `majority_vote` 정책 선택 가능
- **LLM 설명 생성**: Ollama(qwen3.5:9b)로 위험 판단 근거를 한국어로 설명
- **운영자 심사 시스템**: PENDING → 승인/삭제/보류/모니터링 워크플로우
- **심사 결과 재변경**: 이미 심사한 콘텐츠의 판단을 이력 페이지에서 언제든 수정 가능
- **페이지네이션**: 콘텐츠 목록 API에 `limit` / `offset` 지원, 프론트엔드 숫자 페이지 버튼
- **검색**: 텍스트 내용 또는 content_id로 콘텐츠 검색 (300ms 디바운스)
- **자동 새로고침**: 대시보드·심사 큐 30초 주기 자동 갱신 (ON/OFF 토글)
- **CSV 일괄 업로드**: 드래그&드롭으로 CSV 파일 업로드 후 일괄 분석, 저장/중복/오류 건수 반환
- **Active Learning**: 운영자 판단과 모델 예측의 불일치 건을 추출해 재학습 데이터로 활용

## 아키텍처

```
contentguard_ai/
├── backend/                  # FastAPI 백엔드
│   ├── main.py               # 앱 진입점
│   ├── config.py             # 환경변수 설정 (MODEL_PRIMARY, DECISION_POLICY 포함)
│   ├── database.py           # SQLAlchemy DB 연결
│   ├── models.py             # ORM 모델 (contents, model_predictions 테이블)
│   ├── schemas.py            # Pydantic 요청/응답 스키마
│   ├── routers/
│   │   ├── analyze.py              # POST /api/analyze
│   │   ├── contents.py             # GET /api/contents (페이지네이션·검색 지원)
│   │   ├── reviews.py              # POST /api/reviews/{id}
│   │   ├── upload.py               # POST /api/upload/csv (CSV 일괄 업로드)
│   │   └── active_learning.py      # GET /api/active-learning/candidates
│   ├── services/
│   │   ├── prediction_service.py   # ModelRegistry + BaseMLModel 인터페이스
│   │   ├── llm_service.py          # Ollama LLM 설명 생성
│   │   └── risk_service.py         # 등급 분류 / 권장 조치 규칙
│   └── tests/
│       ├── unit/                   # 단위 테스트 (risk_service, prediction_logic, schemas)
│       └── integration/            # 통합 테스트 (analyze, contents, reviews, active_learning)
├── dashboard/                # Next.js 프론트엔드
│   ├── app/
│   │   ├── page.tsx                # 대시보드 (병렬 카운트 조회·차트·자동 새로고침)
│   │   ├── queue/page.tsx          # 심사 큐 (검색·필터·페이지네이션·자동 새로고침)
│   │   ├── analyze/page.tsx        # 콘텐츠 분석 입력
│   │   ├── history/page.tsx        # 전체 이력 (검색·필터·페이지네이션·재변경)
│   │   └── upload/page.tsx         # CSV 일괄 업로드 (드래그&드롭·미리보기·결과)
│   ├── components/
│   │   ├── review-dialog.tsx       # 심사·재변경 공유 다이얼로그
│   │   ├── sidebar.tsx             # 사이드바 내비게이션
│   │   └── ui/                     # Badge, Button, Card, Dialog, Input, Pagination 등
│   └── lib/
│       ├── api.ts                  # FastAPI HTTP 클라이언트 (페이지네이션 응답 처리)
│       └── utils.ts
├── data/
│   ├── training_data.csv     # ML 학습 데이터 500건
│   └── test_data.csv         # 모델 평가용 별도 테스트 데이터 70건 (4등급 고루 분포)
├── models/                   # 학습된 모델 파일
│   ├── tfidf_vectorizer.pkl
│   ├── ridge_model.pkl
│   ├── linear_svm_model.pkl
│   └── logistic_regression_model.pkl
├── scripts/
│   ├── train.py                    # 전체 모델 학습 (Trainer 플러그인 구조)
│   ├── seed_data.py                # 대시보드 테스트용 샘플 데이터 DB 전송 (20건)
│   └── export_active_learning.py   # Active Learning 후보 CSV 내보내기
├── .env                      # 환경변수 (로컬용, git 제외)
├── .env.example              # 환경변수 템플릿
├── docker-compose.yml        # PostgreSQL 17 + pgAdmin 컨테이너
└── requirements.txt          # Python 패키지 목록
```

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | FastAPI, Uvicorn |
| 데이터베이스 | PostgreSQL 17 (Docker), SQLAlchemy ORM |
| ML 모델 | scikit-learn (TF-IDF + Ridge / LinearSVR / Logistic Regression) |
| LLM | Ollama (qwen3.5:9b), 로컬 실행 |
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS |
| 인프라 | Docker Compose |

## ML 모델 구조

### 모델 인터페이스

```python
class BaseMLModel(ABC):
    name: str
    version: str
    model_type: str
    is_primary: bool

    @abstractmethod
    def predict(self, text: str) -> dict: ...
```

새 모델 추가 시 `BaseMLModel`을 상속한 클래스를 작성하고 `TRAINERS` / `ModelRegistry`에 등록하면 됩니다.

### 등록된 모델

| 모델 | 역할 | 등급 정확도 |
|------|------|------------|
| `logistic_regression` | primary (최종 판단) | 90% |
| `linear_svm` | shadow | 77% |
| `tfidf_ridge` | shadow | 62% |

### Decision Policy

`DECISION_POLICY` 환경변수로 최종 판단 방식을 설정합니다.

| 정책 | 동작 |
|------|------|
| `primary_only` | primary 모델 결과만 사용 (기본) |
| `conservative` | 전체 모델 중 가장 높은 위험 점수 채택 |
| `ensemble_mean` | 전체 모델 점수 평균 |
| `majority_vote` | 위험 등급 다수결 (동률 시 높은 등급 우선) |

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

* 심사 완료 후에도 이력 페이지에서 판단 재변경 가능
```

## 시작하기

### 사전 요구사항

- Python 3.10+
- Node.js 18+
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
DATABASE_URL=postgresql+psycopg2://admin:admin@localhost:5434/contentguard_db
OLLAMA_BASE_URL=http://172.18.144.1:11434
OLLAMA_MODEL=qwen3.5:9b
MODEL_PRIMARY=logistic_regression
DECISION_POLICY=primary_only
```

> WSL에서 Windows Ollama에 접근할 때는 `ip route | grep default`로 게이트웨이 IP를 확인하여 OLLAMA_BASE_URL에 사용하세요.

### 2. 패키지 설치

```bash
# 백엔드 (WSL)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 프론트엔드
cd dashboard
npm install
```

### 3. PostgreSQL 실행

```bash
# PowerShell (Windows)
docker compose up -d
```

pgAdmin: http://localhost:5051 (admin@admin.com / admin)

### 4. ML 모델 학습

```bash
# WSL
python scripts/train.py
```

Ridge / Linear SVM / Logistic Regression 3개 모델을 동시에 학습하고 저장합니다.

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
# dashboard 디렉토리
npm run dev
```

대시보드: http://localhost:3000

### 8. 테스트 데이터 주입 (선택)

대시보드에 표시할 샘플 데이터가 없을 때 실행합니다. 백엔드가 실행 중이어야 합니다.

```bash
# WSL (contentguard_ai/ 루트에서)
python scripts/seed_data.py

# 백엔드가 다른 주소에서 실행 중인 경우
python scripts/seed_data.py --url http://0.0.0.0:8000
```

LOW / MEDIUM / HIGH / CRITICAL 각 5건씩 총 20건이 DB에 저장됩니다.

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/api/analyze` | 콘텐츠 위험도 분석 (전체 모델 실행) |
| GET | `/api/contents` | 콘텐츠 목록 조회 |
| GET | `/api/contents/{id}` | 콘텐츠 단건 조회 |
| GET | `/api/contents/{id}/predictions` | 콘텐츠별 모델 예측 결과 조회 |
| POST | `/api/reviews/{id}` | 운영자 심사 결과 제출 (재변경 포함) |
| POST | `/api/upload/csv` | CSV 파일 일괄 업로드 및 분석 |
| GET | `/api/active-learning/candidates` | 재학습 후보 데이터 조회 |

### GET /api/contents 쿼리 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `status` | string | - | 심사 상태 필터 (PENDING / APPROVED / REMOVED / HELD / MONITORED) |
| `risk_level` | string | - | 위험 등급 필터 (LOW / MEDIUM / HIGH / CRITICAL) |
| `sort_by` | string | created_at | 정렬 기준 (`risk_score` 또는 `created_at`) |
| `search` | string | - | 텍스트·content_id 부분 검색 (대소문자 무시) |
| `limit` | int | 20 | 페이지 크기 (1~200) |
| `offset` | int | 0 | 페이지 오프셋 |

응답 헤더 `X-Total-Count`에 필터 적용 후 전체 건수가 포함됩니다.

```bash
# 위험도 높은 순으로 PENDING 콘텐츠 2페이지 조회
GET /api/contents?status=PENDING&sort_by=risk_score&limit=20&offset=20

# "사기" 텍스트 검색
GET /api/contents?search=사기

# CRITICAL 등급 필터
GET /api/contents?risk_level=CRITICAL

# 모델-운영자 불일치 건만 조회 (재학습 후보)
GET /api/active-learning/candidates?disagreement_only=true
```

## 대시보드 페이지

| 페이지 | 기능 |
|--------|------|
| 대시보드 | 전체 통계(병렬 카운트 조회), 위험 등급 분포 차트, 최근 분석 내역 5건, 30초 자동 새로고침 |
| 심사 큐 | 검색, 위험도순 정렬, 등급 필터, 페이지 크기 선택, 페이지네이션, 모델별 예측 상세, 운영자 판단, 30초 자동 새로고침 |
| 콘텐츠 분석 | 텍스트 직접 입력 후 즉시 AI 분석, 모델별 예측 결과 표시 |
| 전체 이력 | 검색, 상태별 필터, 페이지 크기 선택, 페이지네이션, AI 설명·운영자 메모 조회, 심사 결과 재변경 |
| CSV 업로드 | CSV 드래그&드롭 업로드, 미리보기, 일괄 분석, 저장/중복/오류 결과 표시 |

## Active Learning (모델 재학습)

운영자 심사 결과를 모델 재학습에 활용하는 워크플로우입니다.

```bash
# 1. 불일치 후보 내보내기
python scripts/export_active_learning.py

# 전체 심사 완료 건 포함 시
python scripts/export_active_learning.py --all

# 2. 모델 재학습
python scripts/train.py
```

불일치 건의 재학습 점수는 운영자 결정 기준으로 자동 산출됩니다:

| 운영자 결정 | 재학습 점수 |
|------------|------------|
| approve | 0.10 (LOW) |
| monitor | 0.44 (MEDIUM) |
| hold | 0.72 (HIGH) |
| remove | 0.92 (CRITICAL) |

## 새 모델 추가 방법

### 1. `scripts/train.py` — Trainer 클래스 작성 후 등록

```python
class NewModelTrainer(BaseTrainer):
    model_name = "New Model"
    save_file  = "new_model.pkl"

    def fit(self, X_train, y_train_score, y_train_level): ...
    def evaluate(self, X_test, y_test_score, y_test_level): ...

TRAINERS = [
    RidgeTrainer(),
    LinearSVMTrainer(),
    LogisticRegressionTrainer(),
    NewModelTrainer(),   # ← 추가
]
```

### 2. `backend/services/prediction_service.py` — Model 클래스 작성 후 등록

```python
class NewModel(BaseMLModel):
    name = "new_model"
    version = "v1.0.0"
    model_type = "..."
    is_primary = False

    def predict(self, text: str) -> dict: ...

prediction_service.register(NewModel())
```
