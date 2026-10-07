# ContentGuard AI

텍스트 위험도를 분석하고 운영자의 심사 및 고객 서비스 연동을 지원하는 시스템입니다.
최종 승인·삭제·보류·모니터링 결정은 운영자가 수행합니다.

## 구성

- FastAPI / SQLAlchemy / PostgreSQL / Alembic 백엔드
- Next.js 16 / React 19 / TypeScript 대시보드 (Docker·CI: Node.js 24)
- Ollama / OpenAI / Anthropic / Gemini / DeepSeek 분석·추출 공급자
- Firecrawl 및 BeautifulSoup → Trafilatura → LLM 텍스트 추출
- DB에 저장하는 심사 변경 이력과 웹훅 발송 큐, 별도 웹훅 worker
- 분석 작업 큐와 별도 analysis worker, 재분석 이력, 명시적 평가 정답
- 고객별 정책, 고객 전용 현황 화면, CSV/XLSX 대량 접수

현재 신규 분석은 LLM과 규칙을 사용합니다. 기존 `ModelPrediction` 데이터는 이전 모델 예측 조회용으로 보존합니다.
`MODEL_PRIMARY`, `DECISION_POLICY`는 현재 분석 설정이 아닙니다. 파일 업로드 API는 제공하지 않습니다.

## 시작하기

신규 환경에서 `.env.example`을 `.env`로 복사하고 값을 채웁니다. 기존 환경에서는 `.env`를 덮어쓰지 말고 새 항목을 추가하세요.

| 설정 | 용도 |
|---|---|
| `JWT_SECRET_KEY` | 무작위 서명키. 최소 32바이트, 누락 시 시작 실패 |
| `POSTGRES_PASSWORD` | Compose DB 비밀번호. 필수 |
| `OPERATOR_EMAIL`, `OPERATOR_PASSWORD` | 운영자 테이블이 비어 있을 때 초기 계정 생성 |
| `LLM_PROVIDER_EXTRACT`, `LLM_PROVIDER_EXPLAIN` | `ollama`, `openai`, `anthropic`, `gemini`, `deepseek` 중 선택 |
| `LLM_MODEL_EXTRACT`, `LLM_MODEL_EXPLAIN` | 해당 공급자에서 사용할 모델 |
| `OLLAMA_BASE_URL` | 백엔드 컨테이너에서 접근 가능한 Ollama 주소 |
| `DATABASE_URL` | 로컬 Python 실행용 DB URL. Compose에서는 내부 DB URL로 재정의 |
| `FIRECRAWL_API_KEY` | 웹 크롤링 사용 시 필요 |
| `LLM_DEEP_ANALYSIS` | HIGH/CRITICAL 추가 분석 여부. 기본 `false` |
| `ALLOWED_ORIGINS` | 쉼표로 구분한 브라우저 허용 출처 |

서명키와 DB 비밀번호는 각각 새로 생성하세요. hex 비밀번호는 DB URL에 그대로 사용할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d --build
```

- 대시보드: http://localhost:3003
- `DASHBOARD_PORT`로 대시보드 포트를 변경할 수 있습니다. 변경한 주소를 `ALLOWED_ORIGINS`에도 추가하세요.
- API 문서: http://localhost:8003/docs
- `PUBLIC_API_URL`은 고객에게 표시하는 API 연동 주소입니다. 컨테이너 내부 프록시 주소는 별도 `API_INTERNAL_URL`을 사용합니다.
- DB: 로컬 머신의 `127.0.0.1:5434`
- 백엔드 시작 명령은 `alembic upgrade head` 이후 서버를 실행합니다.
- `webhook-worker`는 백엔드 준비 완료 후 실행되어 미전송 건을 처리합니다.
- `analysis-worker`는 오래 걸리는 분석 작업과 재분석을 처리합니다.
- pgAdmin은 `PGADMIN_PASSWORD`를 설정한 뒤 `docker compose --profile tools up -d pgadmin`으로 실행합니다.
- 데모는 `DEMO_CLIENT_API_KEY`, `DEMO_WEBHOOK_SECRET`을 설정한 뒤 `--profile demo`로 실행합니다.

기존 PostgreSQL 볼륨의 비밀번호는 환경변수만 바꿔서는 변경되지 않습니다. 기존 DB 자격증명과 설정을 일치시키거나 DB 비밀번호를 별도로 변경해야 합니다.

Windows의 WSL 내부 Docker를 사용하는 경우, 실행 세션이 모두 종료되면 WSL과 컨테이너가 종료될 수 있습니다. `powershell -ExecutionPolicy Bypass -File scripts/start-wsl-runtime.ps1`은 숨겨진 WSL 프로세스로 실행을 유지합니다. Windows 재부팅 후에는 다시 실행해야 하며, 자동 시작 작업은 등록하지 않습니다. Docker 서비스가 활성화되어 있으면 기존 컨테이너는 재시작 정책에 따라 실행됩니다.

## 분석 동작

1. 공백만 있는 입력을 거부하고 최대 8,000자로 제한합니다. 허용한 입력을 800자로 자르지 않습니다.
2. 개인정보 패턴을 마스킹하고 키워드·규칙을 탐지합니다.
3. LLM의 점수, 등급, 카테고리, 설명 및 인용을 검증합니다. 점수 누락·등급 불일치·원문에 없는 인용은 실패로 처리합니다.
4. 직접 위협 등의 규칙은 최소 등급을 적용합니다. 모호한 키워드·인용·로그인 URL 등은 별도 검토 신호로 처리합니다.
5. 최종 등급이 올라간 이유를 설명에 추가합니다. LLM 실패는 `explanation_json.analysis_status="fallback"`으로 표시하고 운영자 검토를 요구합니다.
6. 마스킹된 텍스트와 그 텍스트 기준의 근거 위치를 저장합니다. 심층 분석과 LLM 추출에도 마스킹을 적용합니다.

| 점수 | 등급 | 기본 권장 조치 |
|---|---|---|
| 0.00–0.29 | LOW | APPROVE |
| 0.30–0.59 | MEDIUM | MONITOR |
| 0.60–0.84 | HIGH | REVIEW |
| 0.85–1.00 | CRITICAL | HOLD |

권장 조치는 자동 집행되지 않습니다. 분석 결과의 초기 심사 상태는 항상 `PENDING`입니다.
마스킹은 전화번호·이메일·주민번호·카드번호 패턴을 대상으로 하며 모든 형태의 개인정보를 식별하는 것은 아닙니다.
기존 DB 원문은 마이그레이션에서 자동 변경하지 않습니다. 과거 데이터의 마스킹·보관 기간은 별도로 정해야 합니다.

긴 분석은 `POST /api/jobs/analyze`로 접수하고 `GET /api/jobs/{id}`로 상태를 조회할 수 있습니다.
작업은 `PENDING → PROCESSING → COMPLETED` 또는 `FAILED/CANCELLED/DEGRADED` 상태를 가집니다.
LLM 임시 결과는 최대 3회 자동 재시도하고, 이후에는 `DEGRADED`로 표시해 수동 재시도를 제공합니다.
180초 작업 점유를 30초마다 갱신하며, 실행 소유 토큰이 일치하는 워커만 결과를 저장합니다. 결과·분석 이력·작업 완료는 같은 트랜잭션입니다.
작업 입력은 DB 저장 전에 개인정보 패턴을 마스킹합니다. 탐지한 개인정보 유형은 별도 저장하여 분석 규칙에 반영합니다.
운영자 재분석은 기존 심사 결정을 덮어쓰지 않고 `needs_re_review`로 다시 심사해야 함을 표시합니다.

분석 실행마다 모델·프롬프트·정책 버전, 처리 시간, 판정·설명 스냅샷을 저장합니다.
운영자가 명시적으로 등록한 정답만 AI 평가에 사용하며, 승인·보류·삭제 조치를 정답 등급으로 변환하지 않습니다.
평가 화면의 정확도·고위험 정밀도·재현율은 정상 완료된 분석과 등록된 정답의 비교입니다.
임시 분석과 과거 상태 미기록 데이터는 수치에서 제외하고 제외 건수를 표시합니다.
평가 화면에서 정답을 고정 데이터셋으로 저장하고 공급자·모델·프롬프트·정책 버전별 보고서를 생성할 수 있습니다.
각 보고서는 선택한 분석 실행 ID와 지표를 보존하므로 이후 재분석·정답 변경의 영향을 받지 않습니다.
현재 현황과 고정 보고서는 구분해서 표시하며, 버전 비교 시 평가 건수와 제외 건수도 확인해야 합니다.

## 인증과 콘텐츠 식별

- 클라이언트: `/auth/signup` 또는 `/auth/login`으로 JWT를 받아 `/auth/keys`에서 API 키를 발급합니다.
- 운영자: `/auth/operator/login`을 사용합니다. 로그인 화면에서 계정 유형을 선택할 수 있습니다.
- 분석·크롤링은 클라이언트 API 키 또는 운영자 인증을 허용합니다.
- 만료된 브라우저 토큰과 401 응답은 재로그인으로 처리합니다.
- API 키는 원문 대신 해시를 저장하며 발급 시 한 번만 표시합니다.
- `ADMIN_SECRET`은 기존 연동용입니다. 심사 이력에서 사용자를 식별하려면 운영자 JWT를 사용하세요.

`content_id`는 **고객 안에서 유일한 외부 식별자**입니다. 다른 고객은 같은 ID를 사용할 수 있습니다.
응답의 `id`는 시스템 내부 레코드 번호입니다. 운영자 조회·심사·삭제 요청에는 `?record_id=<id>`를 함께 사용합니다.
기존 경로는 유일하게 식별할 수 있을 때 계속 동작하며, 같은 ID가 여러 고객에 존재하면 409를 반환합니다.
클라이언트 상태 조회는 자신의 데이터만 검색하며 다른 고객 데이터는 404로 처리합니다.

## 주요 API

| 메서드·경로 | 설명 |
|---|---|
| `POST /api/analyze` | `{content_id, text}` 분석 |
| `POST /api/crawl` | `{url, max_items}` 수집·분석, SSE 응답 |
| `GET /api/contents/{content_id}/status` | 클라이언트 자신의 심사 상태 |
| `GET /api/contents` | 운영자 검색·필터·페이지 조회 |
| `GET /api/contents/{content_id}?record_id=...` | 운영자 상세 조회 |
| `GET /api/contents/{content_id}/analyses?record_id=...` | 분석 실행 이력 |
| `POST /api/contents/{content_id}/reanalyze?record_id=...` | 운영자 재분석 작업 접수 |
| `POST /api/jobs/analyze`, `GET /api/jobs/{id}` | 비동기 분석 접수·상태 조회 |
| `POST /api/jobs/{id}/retry`, `/cancel` | 실패 재시도·진행 작업 취소 |
| `GET /api/jobs` | `limit`, `offset`, `status`, `search`, `client_id`, `batch_id` 필터와 `X-Total-Count` |
| `POST /api/jobs/retry` | `{job_ids}` 최대 100개 선택 재시도, 항목별 실패 반환 |
| `PUT /api/evaluations/labels/{record_id}`, `GET /api/evaluations/summary` | 정답 등록·품질 지표 |
| `GET/POST /api/evaluations/datasets` | 고정 정답 데이터셋 목록·저장 (최대 10,000건) |
| `GET/POST /api/evaluations/datasets/{id}/reports` | 분석 버전 조건별 평가 보고서 목록·저장 |
| `GET/PUT /api/policies/{client_id}`, `POST /api/policies/{client_id}/preview` | 고객별 정책과 변경 예상 |
| `POST /api/batches/preview`, `POST /api/batches`, `GET /api/batches` | CSV/XLSX 미리보기·대량 접수·현황 |
| `GET /api/batches/{id}/errors.csv` | 원본 행 번호와 제외 사유 다운로드 |
| `GET /auth/dashboard`, `/auth/contents`, `/auth/webhooks` | 고객 본인 데이터 현황 |
| `GET /auth/contents/{record_id}`, `POST /auth/contents/{record_id}/retry` | 고객 본인 상세·임시 결과 재분석 |
| `DELETE /api/contents/{content_id}?record_id=...` | 콘텐츠 삭제. 심사 변경 이력은 보존 |
| `POST /api/reviews/{content_id}?record_id=...` | `{action, comment, expected_version, expected_analysis_version}` 심사 |
| `GET /api/reviews/{content_id}/history?record_id=...` | 최근 심사 변경 이력 100건 |
| `GET /api/active-learning/candidates` | 모델·운영자 판단 불일치 후보 |
| `/admin/clients`, `/admin/clients/{id}/keys` | 고객·API 키 관리 |
| `PATCH /admin/clients/{id}/webhook` | 웹훅 주소 설정 |
| `GET /admin/clients/{id}/webhook-secret` | 운영자에게 해당 고객의 서명키 반환 |
| `GET /admin/webhooks` | 최근 발송 상태 100건 |
| `POST /admin/webhooks/{id}/retry` | 최종 실패한 발송 재예약 |
| `GET /health`, `GET /ready` | 의존성 상태 및 DB 준비 상태 |
| `GET /api/operations` | 운영자용 워커 생존 상태·장기 대기·실패 작업 경고 |

심사 요청에 조회한 `review_version`을 `expected_version`으로, `analysis_version`을 `expected_analysis_version`으로 전달합니다.
둘 중 하나가 오래되었으면 409로 거절합니다. 분석 버전을 생략한 기존 호출은 최초 분석에만 허용하며, 재분석된 결과에는 분석 버전이 필수입니다.
고객에게 콘텐츠가 남아 있으면 고객 삭제는 409입니다. 콘텐츠가 없는 고객을 삭제하면 API 키도 함께 삭제됩니다.

고객 정책은 카테고리 점수가 설정한 기준을 넘으면 최소 위험 등급을 올리거나 직접 검토를 요구합니다.
기본 규칙을 낮추지 않으며, 변경은 이후 분석과 재분석부터 적용됩니다. 미리보기는 최근 100건의 기본 규칙 적용 결과에 새 고객 정책을 적용합니다.
과거 고객 정책에 의한 상향을 제거하는 경우도 비교하며, 기준 결과를 복원할 수 없는 과거 데이터는 제외 건수로 표시합니다.

CSV/XLSX 업로드는 최대 2MB·500개 데이터 행·50열입니다. 빈 행을 포함한 물리 행은 5,000개, XLSX 압축 해제 크기는 20MB로 제한합니다.
파싱 중 한도를 넘으면 즉시 중단합니다. 첫 행의 열 이름에서 콘텐츠 ID·텍스트 열을 선택하고 미리보기 후 접수합니다.
파일 원본은 보관하지 않고 유효 행을 개별 분석 작업으로 저장합니다. 제외 사유와 원래 행 번호는 CSV로 내려받을 수 있습니다.
유효 행이 0건이어도 오류 내역을 확인할 수 있도록 접수 기록을 남깁니다. 배치별 작업 필터·페이지 조회·실패 작업 선택 재시도를 지원합니다.
고객은 `/my-dashboard`, `/my-batches`, `/my-jobs`에서 자신의 상세 결과·상태·작업을 확인합니다.

워커는 15초마다 생존 신호를 기록합니다. 60초 이상 갱신되지 않으면 `/health`가 저하 상태를 표시하고,
대시보드는 워커 중단·5분 이상 대기·점유 만료·실패/임시 결과·웹훅 실패를 안내합니다. 외부 알림 발송은 하지 않습니다.

## 웹훅 수신 계약

심사 변경·변경 이력·발송 예약을 하나의 DB 트랜잭션으로 저장합니다.
별도 worker가 발송하며 비정상 HTTP 응답과 연결 실패는 최대 5회까지 재시도합니다.
프로세스 중단으로 임대한 작업은 60초 후 회수됩니다. 중복 전달이 가능하므로 수신 측에서도 중복과 순서를 처리해야 합니다.

```json
{
  "event_id": "고유 이벤트 ID",
  "content_id": "review-001",
  "review_status": "APPROVED",
  "review_action": "approve",
  "review_version": 2,
  "reviewed_at": "2026-09-22T00:00:00+00:00"
}
```

- `X-ContentGuard-Event`: 재시도에도 유지되는 이벤트 ID
- `X-ContentGuard-Timestamp`: 발송 시각의 Unix 초
- `X-ContentGuard-Signature`: `sha256=` + HMAC-SHA256 hex
- 서명 대상: `timestamp`의 UTF-8 바이트 + `.` + **수신한 원본 HTTP body 바이트**
- 키: 고객의 `webhook_secret` 문자열을 UTF-8로 인코딩한 값. hex 디코딩하지 않습니다.

수신자는 서명을 상수 시간 비교하고 허용 시간차(데모는 5분)를 검사해야 합니다.
같은 이벤트는 한 번만 적용하고, 콘텐츠별로 이미 적용한 `review_version`보다 오래된 변경을 무시하세요.
`demo-receiver/main.py`에 서명·시간차 검증과 버전 기반 중복/역순 처리 예제가 있습니다.
대시보드의 API 키 관리에서 서명키를 복사하고 발송 현황 및 재시도를 관리할 수 있습니다.
등록 URL은 운영자가 관리하는 신뢰할 수 있는 수신 주소를 사용하세요. worker는 리다이렉트를 따라가지 않습니다.

로컬 실행에서는 백엔드와 별도로 다음 프로세스가 필요합니다.

```bash
cd backend
python webhook_worker.py
python analysis_worker.py
```

## 검증

```bash
python -m pytest -q --tb=short
cd dashboard
npm ci
npm test
npm run build
```

기본 백엔드 통합 테스트는 외래키 검사를 켠 SQLite를 사용합니다.
PostgreSQL에서는 폐기 가능한 `contentguard_test` DB를 만들고 `TEST_DATABASE_URL`을 지정합니다.
테스트는 해당 DB 테이블을 생성·삭제하므로 운영 DB를 지정하지 마세요.
GitHub Actions는 PostgreSQL 17 통합 테스트와 깨끗한 체크아웃의 프런트엔드 테스트·빌드를 수행하도록 구성되어 있습니다.
마이그레이션 테스트는 기존 레코드와 예측 연결을 보존한 업그레이드·다운그레이드를 검증합니다.

## 기존 환경 업그레이드

이전 마이그레이션 `e91a2b4c630f`는 고객별 ID 제약, 예측의 내부 레코드 참조,
고객별 웹훅 서명키, 심사 버전·이력, 웹훅 발송 테이블을 추가했습니다.
추가 마이그레이션 `f6c20d9a7b41`부터 `d27f9e4056ac`까지는 분석 이력·평가 정답·분석 작업·고객 정책·대량 접수 테이블을 추가합니다.
운영 DB 백업 후 마이그레이션을 적용하고 백엔드·대시보드·worker를 함께 갱신하세요.
여러 고객에 동일한 외부 ID가 생긴 뒤에는 이를 정리하기 전까지 구버전 스키마로 되돌릴 수 없습니다.

## 남은 개선 영역

- 실제 평가 데이터로 카테고리별 오탐·미탐과 인용·우회 표현의 성능 측정
- 분석 작업 큐와 동기 API의 실제 처리량·지연 측정 및 필요 시 워커 확장
- IP 기반 메모리 rate limiter를 운영 토폴로지에 맞춘 계정별·공유 저장소 방식으로 확장
- 과거 원문 및 감사·발송 데이터의 보존 기간과 정리 정책 수립
- 공급자 SDK와 배포 의존성의 재현 가능한 버전 관리
