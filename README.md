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
- **LLM 설명 생성**: 위험 판단 근거를 한국어로 설명. HIGH/CRITICAL은 즉시, MEDIUM/LOW는 백그라운드 생성
- **멀티 LLM 프로바이더**: 텍스트 추출·설명 생성 작업별로 Ollama / OpenAI / Anthropic / Gemini / DeepSeek 독립 설정
- **3단계 하이브리드 텍스트 추출**: BeautifulSoup(CSS 패턴) → Trafilatura → LLM 폴백 순으로 댓글·리뷰 추출
- **운영자 심사 시스템**: PENDING → 승인/삭제/보류/모니터링 워크플로우
- **심사 결과 재변경**: 이미 심사한 콘텐츠의 판단을 이력 페이지에서 언제든 수정 가능
- **콘텐츠 삭제**: 운영자가 이력 페이지에서 콘텐츠 레코드 및 관련 예측 결과 일괄 삭제
- **아웃바운드 웹훅**: 심사 완료 시 클라이언트 서비스로 자동 POST 발송 (BackgroundTasks 비동기 처리)
- **JWT 인증**: 운영자·클라이언트 계정 분리, 로그인 기반 JWT 발급
- **클라이언트 자가 가입**: 이메일+비밀번호로 회원가입 후 직접 API 키 발급·관리
- **클라이언트 CRUD**: 운영자가 어드민 페이지에서 클라이언트 등록·이름 수정·삭제 가능
- **클라이언트 심사 상태 조회**: API 키로 자신이 제출한 콘텐츠의 심사 결과 조회
- **페이지네이션**: 콘텐츠 목록 API에 `limit` / `offset` 지원, 프론트엔드 숫자 페이지 버튼
- **검색**: 텍스트 내용 또는 content_id로 콘텐츠 검색 (300ms 디바운스)
- **자동 새로고침**: 대시보드·심사 큐 30초 주기 자동 갱신 (ON/OFF 토글)
- **KST 시간 표시**: 프론트엔드에서 UTC 타임스탬프를 한국 시간(KST, +09:00)으로 변환 표시
- **파일 일괄 업로드**: CSV / Excel / JSON / TXT 업로드 후 일괄 분석 (최대 1,000건)
- **웹 크롤링 파이프라인**: Firecrawl 수집 → 3단계 텍스트 추출 → ContentGuard 분석 (SSE 스트리밍)
- **Active Learning**: 운영자 판단과 모델 예측의 불일치 건을 추출해 재학습 데이터로 활용
- **Rate Limiting**: IP 기반 요청 수 제한으로 남용 방지
- **DB 마이그레이션**: Alembic으로 스키마 변경 이력 관리 및 안전한 운영 DB 적용

## 아키텍처

```
contentguard_ai/
├── backend/
│   ├── main.py               # 앱 진입점, 초기 운영자 자동 시드
│   ├── config.py             # 환경변수 설정
│   ├── auth.py               # JWT / API 키 / 운영자 인증
│   ├── limiter.py            # slowapi Rate Limiter
│   ├── database.py           # SQLAlchemy DB 연결
│   ├── models.py             # ORM 모델 (clients, operators, api_keys, contents, model_predictions)
│   ├── schemas.py            # Pydantic 요청/응답 스키마
│   ├── migrations/           # Alembic 마이그레이션
│   ├── routers/
│   │   ├── auth.py                 # POST /auth/signup, /auth/login, /auth/operator/login, /auth/keys
│   │   ├── register.py             # POST /register (레거시 자가 발급)
│   │   ├── analyze.py              # POST /api/analyze, GET /api/contents/{id}/status
│   │   ├── contents.py             # GET /api/contents (운영자 전용)
│   │   ├── reviews.py              # POST /api/reviews/{id} + 웹훅 발송
│   │   ├── upload.py               # POST /api/upload
│   │   ├── crawl.py                # POST /api/crawl (SSE 스트리밍)
│   │   ├── active_learning.py      # GET /api/active-learning/candidates
│   │   └── admin.py                # /admin/* (운영자 전용, 웹훅 URL 관리 포함)
│   ├── services/
│   │   ├── content_service.py      # save_analysis() — DB 저장 공통 로직
│   │   ├── prediction_service.py   # ModelRegistry + BaseMLModel 인터페이스
│   │   ├── llm_service.py          # 멀티 프로바이더 LLM + 3단계 하이브리드 텍스트 추출
│   │   └── risk_service.py         # 등급 분류 / 권장 조치 규칙
│   └── tests/
│       ├── unit/
│       └── integration/
├── dashboard/
│   ├── app/
│   │   ├── login/page.tsx          # 운영자 로그인
│   │   ├── signup/page.tsx         # 클라이언트 회원가입
│   │   ├── my-keys/page.tsx        # 클라이언트 API 키 관리 + 로그아웃
│   │   ├── page.tsx                # 대시보드
│   │   ├── queue/page.tsx          # 심사 큐
│   │   ├── analyze/page.tsx        # 콘텐츠 분석
│   │   ├── history/page.tsx        # 전체 이력
│   │   └── collect/page.tsx        # 데이터 수집 (API·업로드·크롤링)
│   ├── components/
│   │   ├── auth-guard.tsx          # 인증 가드 (역할별 레이아웃·리다이렉트)
│   │   ├── sidebar.tsx             # 사이드바 내비게이션 + 운영자 이름 + 로그아웃
│   │   ├── review-dialog.tsx       # 심사·재변경 다이얼로그
│   │   └── ui/
│   └── lib/
│       ├── api.ts                  # FastAPI HTTP 클라이언트
│       ├── auth.ts                 # JWT 토큰 관리 (localStorage)
│       └── utils.ts
├── demo-receiver/
│   ├── main.py               # 웹훅 수신 데모 서버 (POST /webhook, GET /logs)
│   └── Dockerfile
├── demo.sh                   # 웹훅 E2E 데모 스크립트
├── .env
├── .env.example
├── docker-compose.yml
└── requirements.txt
```

## 기술 스택

| 분류 | 기술 |
|------|------|
| 백엔드 | FastAPI, Uvicorn |
| 인증 | JWT (python-jose), bcrypt (passlib) |
| 데이터베이스 | PostgreSQL 17, SQLAlchemy ORM, Alembic |
| ML 모델 | scikit-learn (TF-IDF + Ridge / LinearSVR / Logistic Regression) |
| LLM | Ollama / OpenAI / Anthropic / Gemini / DeepSeek |
| 텍스트 추출 | BeautifulSoup4, Trafilatura, LLM (3단계 하이브리드) |
| 웹훅 | httpx (비동기 아웃바운드), FastAPI BackgroundTasks |
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS |
| 인프라 | Docker Compose |

## 계정 구조

| 역할 | 인증 방식 | 접근 범위 |
|------|----------|----------|
| **클라이언트** | 이메일+비밀번호 → JWT → API 키 발급 | API 분석 요청, 내 API 키 관리, 심사 상태 조회 |
| **운영자** | 이메일+비밀번호 → JWT | 전체 콘텐츠 검토, 심사, 관리 기능 |

### 클라이언트 흐름

```
POST /auth/signup  →  JWT 발급
POST /auth/login   →  JWT 발급
GET  /auth/keys    →  내 API 키 목록 (JWT 필요)
POST /auth/keys    →  API 키 발급 (JWT 필요)

실제 API 호출:
POST /api/analyze              →  Authorization: Bearer <api_key>
GET  /api/contents/{id}/status →  Authorization: Bearer <api_key>  (자기 콘텐츠만)
POST /api/crawl                →  Authorization: Bearer <api_key>
POST /api/upload               →  Authorization: Bearer <api_key>
```

### 운영자 흐름

```
POST /auth/operator/login          →  JWT 발급
GET    /api/contents                 →  콘텐츠 목록 (operator JWT)
DELETE /api/contents/{id}           →  콘텐츠 삭제 (operator JWT)
POST   /api/reviews/{id}            →  심사 처리 (operator JWT) → 웹훅 자동 발송
GET    /admin/clients               →  클라이언트 목록 (operator JWT)
POST   /admin/clients               →  클라이언트 생성 (operator JWT)
PATCH  /admin/clients/{id}          →  클라이언트 이름 수정 (operator JWT)
DELETE /admin/clients/{id}          →  클라이언트 삭제 (operator JWT)
PATCH  /admin/clients/{id}/webhook  →  웹훅 URL 등록·수정 (operator JWT)
```

## 웹훅

심사 완료 시 해당 클라이언트의 `webhook_url`로 결과를 자동 전송합니다.

### 흐름

```
[클라이언트 서비스]  →  POST /api/analyze  →  [ContentGuard]
                                                    ↓ 운영자 심사
[클라이언트 서비스]  ←  POST webhook_url   ←  [ContentGuard]
        ↓
   실제 DB에서 해당 글 삭제 / 숨김 처리
```

### 웹훅 페이로드

```json
{
  "content_id": "review-001",
  "review_status": "REMOVED",
  "review_action": "remove",
  "reviewed_at": "2026-05-12T15:30:00"
}
```

### 웹훅 URL 등록

대시보드 → **API 키 관리** → 클라이언트 카드 하단 → 웹훅 URL 등록

또는 API:
```bash
curl -X PATCH http://localhost:8000/admin/clients/{id}/webhook \
  -H "Authorization: Bearer <operator_jwt>" \
  -d '{"webhook_url": "https://your-service.com/webhook"}'
```

### 실제 서비스 연동 예시

클라이언트 서비스(예: 쇼핑몰)에서 두 곳만 수정하면 연동됩니다.

**1. 콘텐츠 제출 — 리뷰 저장 시점에 API 호출 추가**

```python
import requests

CONTENTGUARD_URL = "https://contentguard.example.com"
API_KEY = "cg-xxxxxxxxxxxx"  # 어드민에서 발급받은 API 키

def on_review_submitted(review):
    db.save(review)  # 기존 저장 로직

    # ContentGuard에 위험도 분석 요청 (2줄 추가)
    requests.post(f"{CONTENTGUARD_URL}/api/analyze",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"content_id": str(review.id), "text": review.text},
    )
```

**2. 웹훅 수신 — 심사 결과를 받아 실제 DB에 반영**

```python
@app.post("/webhook/contentguard")
def receive_review_result(payload: dict):
    content_id = payload["content_id"]
    status     = payload["review_status"]

    if status == "REMOVED":
        db.hide_review(content_id)    # 게시 중단
    elif status == "APPROVED":
        db.publish_review(content_id) # 정식 게시
    elif status == "HELD":
        db.hold_review(content_id)    # 임시 보류
    elif status == "MONITORED":
        db.flag_review(content_id)    # 모니터링 태그

    return {"ok": True}
```

**3. 웹훅 URL 등록**

대시보드 → **API 키 관리** → 클라이언트 카드 하단에서 등록:
```
https://쇼핑몰.example.com/webhook/contentguard
```

이후 운영자가 심사를 완료하면 쇼핑몰 서버로 결과가 자동 전송되어 실제 DB에 반영됩니다.

---

### 데모 실행

`docker-compose up -d` 실행 시 `demo-receiver` 컨테이너(포트 9000)가 함께 뜨며 웹훅 수신 서버로 동작합니다.

```bash
# .env에 DEMO_CLIENT_API_KEY 설정 후
bash demo.sh
```

실행할 때마다 사기·가품·개인정보 유출·폭언 등 카테고리별 샘플 텍스트 31종 중 하나가 무작위로 선택됩니다. 출력되는 타임스탬프는 KST(한국 시간)로 자동 변환됩니다.

| 항목 | 주소 |
|------|------|
| 웹훅 수신 서버 | http://localhost:9000/webhook |
| 수신 로그 확인 | http://localhost:9000/logs |

## ML 모델 구조

### 등록된 모델

학습 데이터 500개, 테스트셋 100개(20%), TF-IDF char n-gram(2~4) 기준 실측값.

| 모델 | 역할 | 정확도 | F1 (macro) | MAE | R² |
|------|------|:------:|:----------:|:---:|:--:|
| `logistic_regression` | primary (최종 판단) | **90.0%** | **88.7%** | — | — |
| `linear_svm` | shadow | 77.0% | 73.6% | 0.102 | 0.870 |
| `tfidf_ridge` | shadow | 62.0% | 60.1% | 0.134 | 0.808 |

#### Logistic Regression 등급별 성능 (primary 모델)

| 등급 | Precision | Recall | F1 | Support |
|------|:---------:|:------:|:--:|:-------:|
| LOW | 0.94 | 0.83 | 0.88 | 35 |
| MEDIUM | 0.75 | 0.88 | 0.81 | 17 |
| HIGH | 0.88 | 0.88 | 0.88 | 16 |
| CRITICAL | 0.97 | 1.00 | 0.98 | 32 |

### Decision Policy

| 정책 | 동작 |
|------|------|
| `primary_only` | primary 모델 결과만 사용 (기본) |
| `conservative` | 전체 모델 중 가장 높은 위험 점수 채택 |
| `ensemble_mean` | 전체 모델 점수 평균 |
| `majority_vote` | 위험 등급 다수결 |

## 위험 등급 기준

| 등급 | 점수 범위 | 권장 조치 |
|------|-----------|-----------|
| LOW | 0.00 ~ 0.29 | approve (자동 승인) |
| MEDIUM | 0.30 ~ 0.59 | monitor (모니터링) |
| HIGH | 0.60 ~ 0.84 | hold (보류 후 심사) |
| CRITICAL | 0.85 ~ 1.00 | remove (즉시 삭제) |

## 3단계 하이브리드 텍스트 추출

웹 크롤링 시 댓글·리뷰를 정확하게 추출하기 위해 3단계로 시도합니다.

```
1차: BeautifulSoup
     comment / review / reply / feedback 등 CSS 클래스·ID 패턴 탐지
     → 결과 있으면 반환 (가장 빠르고 정확)

2차: Trafilatura
     범용 본문 추출 후 품질 검사 통과 시 반환

3차: LLM 폴백
     마크다운 원문을 LLM에 전달해 사용자 작성 텍스트만 추출
```

## 시작하기

### 사전 요구사항

- Docker (WSL 기반 권장)
- Ollama (Windows에서 실행, `qwen3.5:9b` 모델 권장)

### Docker로 실행 (권장)

```bash
cp .env.example .env
# .env에서 필수 값 설정 (아래 환경변수 참고)

docker compose up -d --build
```

| 서비스 | 주소 |
|--------|------|
| API | http://localhost:8000 |
| API 문서 | http://localhost:8000/docs |
| 대시보드 | http://localhost:3000 |
| pgAdmin | http://localhost:5051 |
| 웹훅 데모 수신 서버 | http://localhost:9000 |

백엔드 시작 시 `alembic upgrade head`가 자동 실행되고, `OPERATOR_EMAIL` / `OPERATOR_PASSWORD`로 초기 운영자 계정이 자동 생성됩니다.

#### Docker 재빌드

```bash
# 백엔드 코드 변경 시
docker compose up -d --build backend

# 대시보드 코드·환경변수 변경 시
docker compose up -d --build dashboard
```

#### Docker 네트워크 구조

```
[브라우저] → localhost:3000 → [dashboard 컨테이너]
                                      ↓ Next.js rewrites (프록시)
                               backend:8000 → [backend 컨테이너]
                                                    ↓
                                             db:5432 → [db 컨테이너]

[backend 컨테이너] → demo-receiver:9000 → [demo-receiver 컨테이너]
                     (심사 완료 시 웹훅 발송)
```

대시보드는 `/api/*`, `/admin/*`, `/auth/*` 요청을 모두 백엔드로 프록시합니다.

---

### 로컬 개발 (WSL)

#### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 필수 설정:

```env
DATABASE_URL=postgresql+psycopg2://admin:admin@localhost:5434/contentguard_db

# JWT
JWT_SECRET_KEY=랜덤하고-충분히-긴-문자열  # openssl rand -hex 32
OPERATOR_EMAIL=admin@example.com
OPERATOR_PASSWORD=your-password

# LLM (필수)
LLM_PROVIDER_EXTRACT=ollama
LLM_PROVIDER_EXPLAIN=ollama
OLLAMA_BASE_URL=http://172.18.144.1:11434
OLLAMA_MODEL=qwen3.5:9b

# 기타
FIRECRAWL_API_KEY=fc-xxxxxxxx
MODEL_PRIMARY=logistic_regression
DECISION_POLICY=primary_only

# 웹훅 데모 (어드민 페이지에서 발급 후 입력)
DEMO_CLIENT_API_KEY=cg-xxxxxxxx
```

#### 2. 패키지 설치 및 실행

```bash
# 백엔드 (WSL)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd backend && alembic upgrade head
uvicorn main:app --reload --port 8000

# 프론트엔드
cd dashboard && npm install && npm run dev
```

#### 3. 테스트

```bash
pytest
# 200개 이상 테스트 (통합 + 유닛)
```

## 환경변수 전체 목록

| 변수 | 필수 | 설명 |
|------|------|------|
| `DATABASE_URL` | ✅ | PostgreSQL 연결 문자열 |
| `JWT_SECRET_KEY` | ✅ | JWT 서명 키 (충분히 긴 랜덤 문자열) |
| `JWT_EXPIRE_MINUTES` | | JWT 만료 시간 (기본 1440 = 24시간) |
| `OPERATOR_EMAIL` | | 초기 운영자 이메일 (최초 실행 시 자동 생성) |
| `OPERATOR_PASSWORD` | | 초기 운영자 비밀번호 |
| `LLM_PROVIDER_EXTRACT` | ✅ | 텍스트 추출용 LLM 프로바이더 |
| `LLM_MODEL_EXTRACT` | | 추출 모델명 (미설정 시 프로바이더 기본값) |
| `LLM_PROVIDER_EXPLAIN` | ✅ | 설명 생성용 LLM 프로바이더 |
| `LLM_MODEL_EXPLAIN` | | 설명 모델명 (미설정 시 프로바이더 기본값) |
| `OLLAMA_BASE_URL` | | Ollama 서버 주소 |
| `OLLAMA_MODEL` | | Ollama 기본 모델명 |
| `OPENAI_API_KEY` | | OpenAI 사용 시 |
| `ANTHROPIC_API_KEY` | | Anthropic 사용 시 |
| `GEMINI_API_KEY` | | Gemini 사용 시 |
| `DEEPSEEK_API_KEY` | | DeepSeek 사용 시 |
| `FIRECRAWL_API_KEY` | | 웹 크롤링 기능 사용 시 |
| `MODEL_PRIMARY` | | primary 모델명 (기본 `logistic_regression`) |
| `DECISION_POLICY` | | 판단 정책 (기본 `primary_only`) |
| `ALLOWED_ORIGINS` | | CORS 허용 도메인 (기본 `http://localhost:3000`) |
| `ADMIN_SECRET` | | 레거시 운영자 인증 (하위 호환용) |
| `DEMO_CLIENT_API_KEY` | | 웹훅 데모용 클라이언트 API 키 |

## API 엔드포인트

### 인증

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/auth/signup` | 클라이언트 회원가입 → JWT |
| POST | `/auth/login` | 클라이언트 로그인 → JWT |
| POST | `/auth/operator/login` | 운영자 로그인 → JWT |
| GET | `/auth/me` | 내 계정 정보 |
| GET | `/auth/keys` | 내 API 키 목록 (클라이언트 JWT) |
| POST | `/auth/keys` | API 키 발급 (클라이언트 JWT) |
| DELETE | `/auth/keys/{id}` | API 키 비활성화 (클라이언트 JWT) |

### 클라이언트 (API 키 인증)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/analyze` | 콘텐츠 위험도 분석 (60회/시간) |
| GET | `/api/contents/{id}/status` | 내 콘텐츠 심사 상태 조회 |
| POST | `/api/upload` | 파일 일괄 업로드·분석 |
| POST | `/api/crawl` | URL 크롤링·분석 SSE 스트리밍 |

### 운영자 전용 (operator JWT)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/contents` | 콘텐츠 목록 (페이지네이션·검색·필터) |
| GET | `/api/contents/{id}` | 콘텐츠 단건 조회 |
| GET | `/api/contents/{id}/predictions` | 모델별 예측 결과 |
| DELETE | `/api/contents/{id}` | 콘텐츠 및 예측 결과 삭제 |
| POST | `/api/reviews/{id}` | 심사 결과 제출 → 웹훅 자동 발송 |
| GET | `/api/active-learning/candidates` | 재학습 후보 조회 |
| POST | `/admin/clients` | 클라이언트 생성 |
| GET | `/admin/clients` | 클라이언트 목록 |
| PATCH | `/admin/clients/{id}` | 클라이언트 이름 수정 |
| DELETE | `/admin/clients/{id}` | 클라이언트 삭제 (API 키 포함) |
| PATCH | `/admin/clients/{id}/webhook` | 클라이언트 웹훅 URL 등록·수정 |
| POST | `/admin/clients/{id}/keys` | API 키 발급 |
| DELETE | `/admin/keys/{id}` | API 키 비활성화 |
| GET | `/admin/operators` | 운영자 목록 |

> **API 키 인증**: `Authorization: Bearer <api_key>` 헤더
> **JWT 인증**: `Authorization: Bearer <jwt_token>` 헤더

## 대시보드 페이지

| 페이지 | 역할 | 기능 |
|--------|------|------|
| `/login` | 공통 | 운영자·클라이언트 로그인 |
| `/signup` | 클라이언트 | 회원가입 (이메일+비밀번호) |
| `/my-keys` | 클라이언트 | API 키 발급·목록·삭제, 로그아웃 |
| `/` | 운영자 | 전체 통계, 위험 등급 분포 차트, 30초 자동 새로고침 |
| `/queue` | 운영자 | 심사 큐 (검색·필터·페이지네이션·운영자 판단) |
| `/analyze` | 운영자 | 텍스트 직접 입력 후 즉시 AI 분석 |
| `/history` | 운영자 | 전체 이력 (검색·필터·심사 재변경·콘텐츠 삭제) |
| `/collect` | 운영자 | API 연동 가이드·파일 업로드·웹 크롤링 |
| `/admin` | 운영자 | 클라이언트 등록·이름 수정·삭제, API 키 발급·비활성화, 웹훅 URL 관리 |

## LLM 프로바이더 설정

| 프로바이더 | 값 | 필요한 환경변수 | 기본 모델 |
|-----------|-----|----------------|----------|
| Ollama (로컬) | `ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `OLLAMA_MODEL` 값 |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat` |

추출·설명을 서로 다른 프로바이더로 설정할 수 있습니다:

```env
# 텍스트 추출: 로컬 Ollama (비용 절감)
LLM_PROVIDER_EXTRACT=ollama
LLM_MODEL_EXTRACT=qwen2.5:7b

# 설명 생성: Claude Haiku (품질 향상)
LLM_PROVIDER_EXPLAIN=anthropic
LLM_MODEL_EXPLAIN=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

## DB 마이그레이션

```bash
cd backend

# 모델 변경 후 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "설명"

# 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

현재 마이그레이션 이력:
1. `fcd865a7cc83` — 초기 스키마 (clients, api_keys, contents, model_predictions)
2. `a3f192c8d041` — 인증 모델 추가 (clients.email/password_hash, operators 테이블)
3. `b7e4d1f9a023` — 웹훅 추가 (clients.webhook_url)

## Active Learning

```bash
# 불일치 후보 내보내기
python scripts/export_active_learning.py

# 모델 재학습
python scripts/train.py
```

| 운영자 결정 | 재학습 점수 |
|------------|------------|
| approve | 0.10 (LOW) |
| monitor | 0.44 (MEDIUM) |
| hold | 0.72 (HIGH) |
| remove | 0.92 (CRITICAL) |

## 헬스체크

```bash
curl http://localhost:8000/health
# {"status": "ok", "db": "ok", "ollama": "ok"}
```
