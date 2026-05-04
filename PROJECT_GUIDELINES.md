# 📌 Project: ContentGuard AI

## 🧠 Project Overview

ContentGuard AI는 사용자 콘텐츠의 위험도를 분석하고,
생성형 AI가 판단 근거를 설명하며,
운영자가 최종 의사결정을 내릴 수 있도록 지원하는
AI 기반 콘텐츠 리스크 운영 시스템이다.

핵심 구조:
AI (판단) + LLM (설명) + Human (결정)

---

## 🎯 Project Goal

- 단순 ML 모델이 아닌 "운영 시스템" 구현
- AI 결과를 사람이 신뢰하고 활용할 수 있게 만들기
- API 기반 서비스 구조 설계
- Human-in-the-loop 시스템 구현

---

## ⚙️ Tech Stack

### Backend
- FastAPI

### ML
- TF-IDF + Logistic Regression (baseline)
- 향후 XGBoost / Transformer 확장 가능

### LLM
- OpenAI API 또는 Ollama

### Frontend (Dashboard)
- Streamlit

### Database
- PostgreSQL

---

## 🧱 System Architecture

[User / Streamlit]
        ↓
[FastAPI API Server]
        ↓
[ML Model + LLM]
        ↓
[Database]
        ↓
[Review Queue / Dashboard]

---

## 🔄 Core Workflow

1. 콘텐츠 입력 (text)
2. FastAPI `/api/analyze` 호출
3. ML 모델 → risk_score 계산
4. Risk Policy Engine → risk_level 분류
5. LLM → 설명 생성
6. DB 저장
7. Streamlit → 심사 큐 표시
8. 운영자 → 판단 (approve/remove/etc)
9. 피드백 저장

---

## 📌 Key API Design

### POST /api/analyze
입력:
{
  "content_id": "C001",
  "text": "example text"
}

출력:
{
  "risk_score": 0.82,
  "risk_level": "HIGH",
  "explanation": "...",
  "recommended_action": "REVIEW"
}

---

### GET /api/contents
- 전체 콘텐츠 조회

---

### POST /api/reviews/{content_id}
- 운영자 판단 저장

---

## 🎯 Risk Policy

score 기준:

- 0.85 이상 → CRITICAL
- 0.60 이상 → HIGH
- 0.30 이상 → MEDIUM
- 이하 → LOW

---

## 🧠 ML Pipeline

text
→ preprocessing
→ TF-IDF vectorization
→ Linear SVM
→ probability (toxicity_score)

---

## 🤖 LLM 역할

- 모델 결과 설명
- 운영자 의사결정 지원
- 자연어 기반 분석 가능

---

## 🧪 Development Strategy

### Step 1 (MVP)
- FastAPI 기본 서버
- /api/analyze 구현1
- rule-based or simple model

### Step 2
- TF-IDF + Logistic Regression (점수 산정) / Linear SVM (등급 산정) 모델 적용

### Step 3
- DB 저장 기능

### Step 4
- Streamlit 대시보드

### Step 5
- LLM 설명 기능

### Step 6
- 심사 큐 + 피드백 루프

---

## ❗ Important Design Principles

- AI는 판단만 한다 (결정하지 않는다)
- 최종 판단은 사람이 한다
- 설명 가능성(Explainability)을 최우선으로 한다
- 시스템은 "자동화"가 아니라 "의사결정 지원"이다

---

## 🧩 Future Improvements

- XGBoost / BERT 모델 도입
- RAG 기반 설명 개선
- 사용자 행동 데이터 활용
- 실시간 스트리밍 처리 (Kafka)

---

## 💬 For Claude (Instructions)

- 항상 "운영 시스템" 관점에서 설계 제안할 것
- 단순 모델 개선보다 "전체 흐름"을 우선할 것
- 설명 가능성과 UX를 고려할 것
- API 중심 구조 유지할 것

## 🔒 Development Rules & Constraints

### 1. Security Rules

- API 키, 비밀번호, 토큰 등 민감 정보는 절대 코드에 하드코딩하지 않는다.
- 모든 환경 변수는 `.env` 파일을 통해 관리한다.
- `.env` 파일은 Git에 절대 커밋하지 않는다.
- `.env.example` 파일을 제공하여 필요한 환경 변수 구조를 명시한다.

예시:
OPENAI_API_KEY=your_api_key_here

---

### 2. Environment Management

- Python 가상환경(venv)을 사용하여 개발한다.
- 의존성은 `requirements.txt`로 관리한다.
- Docker 도입 시에도 `.env` 기반 환경 변수 방식을 유지한다.

---

### 3. API Design Rules

- 모든 기능은 API 중심으로 설계한다.
- FastAPI 엔드포인트는 명확한 역할을 가져야 한다.
- 요청/응답은 JSON 형식을 사용한다.
- 스키마는 Pydantic 모델로 정의한다.

예시:
- POST /api/analyze
- GET /api/contents
- POST /api/reviews/{content_id}

---

### 4. Code Structure Rules

- 비즈니스 로직은 `services/` 디렉토리에 분리한다.
- API 라우팅은 `routers/` 디렉토리에 분리한다.
- DB 모델은 `models.py`, 스키마는 `schemas.py`에 정의한다.
- 하나의 파일에 모든 로직을 몰아넣지 않는다.

---

### 5. AI/ML Rules

- 모델은 API 내부에 직접 작성하지 않는다.
- 모델 로딩 및 예측 로직은 별도 서비스(`prediction_service.py`)로 분리한다.
- LLM 호출 로직도 별도 서비스(`llm_service.py`)로 분리한다.

---

### 6. Logging & Debugging

- print 대신 logging을 사용한다.
- 주요 API 호출 및 에러는 로그로 기록한다.

---

### 7. Error Handling

- 모든 API는 예외 처리를 포함해야 한다.
- 사용자에게는 명확한 에러 메시지를 반환한다.

---

### 8. Data Handling

- 입력 데이터는 반드시 검증한다 (Pydantic 활용)
- 민감한 사용자 데이터는 저장하지 않는다.
- 로그에 개인정보를 남기지 않는다.

---

### 9. Git Rules

- 의미 있는 단위로 커밋한다.
- 커밋 메시지는 기능 단위로 작성한다.

예시:
feat: add analyze API
fix: handle empty input error

---

### 10. Project Philosophy

- AI는 "판단"만 한다
- LLM은 "설명"한다
- Human이 "결정"한다

이 원칙을 코드 구조에도 반영한다.