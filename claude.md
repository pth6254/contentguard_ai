# ContentGuard AI — Claude 작업 인수인계

작성일: 2026-10-06 (Asia/Seoul)  
대상 작업 폴더: `C:\Users\Laptop PC\Desktop\contentguard_ai`

이 문서는 지금까지의 대화에서 나온 요청, 구현 결과, 운영 반영 및 검증 기록을 요약한 인수인계 자료다. 대화 전문은 아니다. 다음 담당자는 이 문서와 `README.md`, `PROJECT_GUIDELINES.md`를 읽고 실제 변경 내역을 확인한 뒤 이어서 작업한다.

## 1. 바로 알아야 할 현재 상태

- 사용자가 지정한 포트는 **프런트엔드 3003 / 백엔드 8003**이다. 별도 요청 없이 바꾸지 않는다.
- 앞서 승인된 개선 작업은 구현과 현재 로컬 Docker 운영 환경 배포까지 완료했다. 외부 클라우드 운영 서버에 배포했다는 뜻은 아니다.
- 마지막 전체 검증·배포 기록은 **2026-10-05** 기준이다. 2026-10-06에는 인수인계 문서를 만들기 위해 코드·설정·검증 기록을 확인했다. 오늘 서비스의 실제 가동 상태나 전체 테스트를 다시 확인한 것은 아니다.
- 2026-10-06 확인한 Git 브랜치는 `master`, HEAD는 `96d9ae1` (`Use alternate local ports for demo services`)이다.
- 개선 코드와 신규 마이그레이션은 **아직 커밋되지 않았다**. `git status --short`에 다수의 수정 파일과 신규 파일이 있다. 기존 작업을 초기화하거나 덮어쓰지 않는다.
- 현재 요청은 이 `claude.md` 인수인계 파일 제작이다. 아래의 추가 개선 후보는 새 작업 제안이며, 전부 구현하라는 새 지시로 해석하지 않는다.
- 비밀번호·API 키·JWT·운영 본문은 이 문서에 넣지 않았다. 실제 설정은 기존 `.env`를 사용하며 값을 출력하거나 커밋하지 않는다.

## 2. 사용자 요청과 진행 흐름

| 순서 | 대화에서 나온 핵심 요청 | 반영 결과 |
|---|---|---|
| 1 | 프로젝트를 분석하고 문제점·개선점을 알려 달라는 요청 | 코드와 운영 구조를 점검하고 개선 항목을 도출 |
| 2 | “네”, “이어서”로 후속 진행 승인 | 분석 결과에 따라 구현·검증을 이어서 진행 |
| 3 | “운영 DB와 배포에도 적용해보면” | DB 백업, 마이그레이션, 현재 Docker 환경 배포 및 데이터 보존 확인 |
| 4 | 대시보드 포트를 3001에서 3003으로 변경 | 프런트엔드 기본 포트 3003 반영 |
| 5 | 추가할 기능과 기존 기능의 개선점 분석 | 아래 네 단계의 개선 순서를 수립 |
| 6 | “① 실패 표시·일괄 심사·상태 표시 수정 → ② 평가 데이터와 분석 이력 구축 → ③ 작업 큐와 재분석 → ④ 고객별 정책·고객 화면·대량 수집 순서대로 수정 진행해줘” | 해당 기능들을 단계적으로 구현 |
| 7 | “포트 frontend 3003 backend 8003” | 프런트엔드 3003, 백엔드 8003으로 확정 |
| 8 | 추가 개선점 탐색과 후속 “네” | 심사 충돌·큐 안정성·정책 미리보기·평가 재현성·대량 수집·운영 상태·의존성을 추가 개선하고 배포 |
| 9 | “지금까지 진행한 대화내역 인수인계 진행할 파일 제작해봐 claude.md 파일 제작” | 본 문서 작성 |

사용자는 한국어로 소통하며, 제안만 하고 멈추기보다 승인된 작업을 구현·검증·운영 반영까지 마무리하는 방식을 요청했다. 이미 정한 포트와 데이터 보존 조건을 이어받는다.

## 3. 프로젝트 개요와 주요 경로

콘텐츠 텍스트의 위험도를 LLM과 규칙으로 분석하고, 근거를 제시하여 운영자의 최종 심사를 지원하는 서비스다. AI의 권장 조치와 사람의 심사 결과를 분리한다.

| 영역 | 구성 / 주요 파일 |
|---|---|
| 백엔드 | Python 3.12, FastAPI, SQLAlchemy, PostgreSQL 17, Alembic; `backend/main.py`, `backend/models.py`, `backend/schemas.py` |
| 공통 분석 | `backend/services/analysis_service.py`, `content_service.py`, `policy_service.py` |
| 영속 작업 큐 | `backend/services/analysis_job_service.py`, `backend/analysis_worker.py`, `backend/routers/jobs.py` |
| 심사·콘텐츠 | `backend/routers/reviews.py`, `backend/routers/contents.py` |
| 평가·정책 | `backend/routers/evaluations.py`, `backend/routers/policies.py` |
| 고객·대량 수집 | `backend/routers/client_portal.py`, `backend/routers/batches.py` |
| 웹훅·운영 상태 | `backend/webhook_worker.py`, `backend/services/worker_health.py`, `backend/routers/operations.py` |
| 프런트엔드 | Next.js 16.3.8, React 19.3.0, TypeScript, Tailwind CSS 4.3.3; Docker·CI Node.js 24 |
| 공통 UI/API | `dashboard/components/`, `dashboard/lib/api.ts` |
| 배포·CI | `docker-compose.yml`, `backend/Dockerfile`, `dashboard/Dockerfile`, `.github/workflows/checks.yml` |
| 개발 지침 | `PROJECT_GUIDELINES.md`, 실행·API 안내는 `README.md` |

신규 분석에는 과거 TF-IDF/앙상블 모델이나 Streamlit을 사용하지 않는다. `ModelPrediction`은 과거 예측 데이터 조회를 위해 남아 있다. 현재 분석 경로를 고칠 때 과거 모델 코드만 수정하는 실수를 피한다.

## 4. 완료한 주요 기능과 반드시 유지할 동작

### 4.1 실패 표시·심사·분석 이력

- LLM 실패를 정상 LOW 결과로 숨기지 않고 `explanation_json.analysis_status="fallback"`으로 구분한다.
- 일괄 심사와 상태 표시, 분석 실행 이력 및 명시적 평가 정답을 제공한다.
- `Content`, `AnalysisRun`, `ReviewEvent`에 `analysis_version`을 추가했다.
- 심사 요청은 조회 시 받은 `review_version`을 `expected_version`으로, `analysis_version`을 `expected_analysis_version`으로 보낸다. 오래된 버전이면 HTTP 409로 거절한다.
- 과거 API 호환을 위해 분석 버전 생략은 최초 분석에만 허용한다. 재분석된 결과에서는 분석 버전이 필수다.
- 재분석은 기존 심사 결정을 보존하고 `needs_re_review`로 다시 심사할 필요를 표시한다.
- 마스킹된 본문과 근거 위치를 함께 갱신한다. Python 코드포인트와 JavaScript UTF-16 인덱스 차이도 고려한다.

### 4.2 작업 큐·재분석·동시 실행 안정성

- 분석을 DB에 저장하는 작업 큐와 별도 `analysis-worker`로 처리한다.
- 상태는 `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `CANCELLED`, `DEGRADED`로 구분한다.
- LLM fallback은 최대 3회 시도 후 `DEGRADED`로 남겨 수동 재시도를 허용한다.
- 작업 점유 기간은 180초이며, 별도 세션으로 30초마다 갱신한다. 결과 저장 시 `lease_token`과 `PROCESSING` 상태를 확인하여 점유권을 잃은 워커의 결과를 버린다.
- 외부 모델 응답을 기다리는 동안 DB 트랜잭션·연결을 계속 점유하지 않는다.
- 콘텐츠 결과, 분석 이력, 작업 완료를 하나의 트랜잭션으로 저장한다.
- 재시도·취소는 행 잠금과 같은 레코드의 활성 작업 확인을 거친다.
- 재분석 큐에 넣기 전 과거 본문도 마스킹하고 감지된 개인정보 유형을 보존한다.
- 작업 검색, 상태·고객·배치 필터, 페이지 조회, 최대 100개 선택 재시도와 항목별 결과를 제공한다.
- 공통 UI는 `dashboard/components/jobs-panel.tsx`; 운영자 `/jobs`, 고객 `/my-jobs`에서 사용한다.

### 4.3 고객 정책·평가 재현성

- 고객 정책을 적용하기 전의 기본 판정을 `base_decision`으로 저장하고 적용 정책의 스냅샷도 분석 메타데이터에 남긴다.
- 정책 미리보기는 기존 고객 정책으로 이미 올라간 등급이 아니라 기본 판정에서 시작한다. 이전 고객 정책의 상향 효과를 제거하는 경우도 비교하며, 공통 안전 규칙의 최소 등급은 유지한다.
- 기본 판정을 복원할 근거가 부족한 과거 데이터는 미리보기에서 제외하고 제외 건수를 표시한다.
- 평가 정답을 고정하는 `EvaluationDataset`과 필터·분석 실행 ID·지표를 고정하는 `EvaluationReport`를 추가했다.
- 데이터셋은 최대 10,000건이다. 보고서는 생성 시점에 공급자·모델·프롬프트·정책 버전 조건에 맞는 콘텐츠별 최신 실행을 선택하고 결과를 보존한다.
- 현재 상태 요약과 고정 보고서를 UI에서 구분하고 평가·제외 건수를 표시한다.
- 운영자의 승인·보류·삭제는 AI 평가 정답으로 자동 변환하지 않는다. 명시적으로 등록한 정답만 사용한다.
- 2026-10-05 운영 DB 확인 당시 평가 정답은 0건이었다. 평가 기능 구축 완료를 실제 모델 품질 검증 완료로 해석하지 않는다.

### 4.4 고객 화면·대량 수집

- 고객은 `/my-dashboard`, `/my-batches`, `/my-jobs`에서 본인 데이터만 조회한다.
- 고객 상세에서 근거·카테고리·설명·임시 결과·재심사 필요 상태를 표시하며 임시 결과의 재분석을 요청할 수 있다.
- 고객 대시보드는 10초마다 갱신하고 이전 요청의 늦은 응답으로 화면이 되돌아가지 않도록 처리했다.
- CSV/XLSX 제한: 파일 2MB, 데이터 500행, 50열, 빈 행 포함 물리 행 5,000개, 셀 8,000자, 헤더 100자.
- XLSX는 압축 해제 크기 20MB, ZIP 항목 1,000개 제한을 적용한다. 파싱 중 한도를 검사하고 이벤트 루프 밖에서 처리한다.
- 원래 행 번호를 보존하고 오류에는 행 번호·사유만 기록한다. 파일 본문을 오류 보고서에 복사하지 않는다.
- 데이터 행이 있지만 모두 잘못된 경우에도 접수 기록과 오류 CSV를 제공한다.
- 배치 목록 페이지 조회, 배치별 작업 이동, 고객 권한을 적용한 오류 CSV 다운로드를 지원한다.

### 4.5 운영 상태·보안·의존성

- 분석·웹훅 워커는 15초마다 heartbeat를 기록하고 60초 이상 갱신되지 않으면 offline으로 표시한다.
- `/health`는 DB·필요 시 Ollama·워커 상태를 확인한다. 클라우드 LLM만 쓰면 Ollama 확인을 생략한다.
- `/ready`는 DB 준비 상태를 확인한다. 워커 시작과 백엔드 준비 확인의 순환 의존성을 만들지 않는다.
- 운영자 전용 `/api/operations`에서 큐 상태, 5분 이상 대기, 만료된 점유, 24시간 실패·임시 결과 비율, 웹훅 실패와 경고를 제공한다.
- 외부 알림 발송은 구현하지 않았다. 현재 알림은 대시보드에 표시한다.
- Next.js·React·Tailwind 및 관련 의존성을 갱신하고 Docker·CI Node를 24로 맞췄다. CI에 `npm audit --audit-level=high`를 추가했다.
- 내부 프록시 `API_INTERNAL_URL`과 고객에게 표시할 `NEXT_PUBLIC_API_URL`을 분리했다. Compose에서는 공개 주소를 `PUBLIC_API_URL`로 지정한다.

## 5. 주요 API와 데이터 계약

전체 목록은 `README.md`와 `/docs`를 확인한다. 이어서 작업할 때 특히 필요한 경로는 다음과 같다.

| 용도 | API |
|---|---|
| 비동기 분석 | `POST /api/jobs/analyze`, `GET /api/jobs/{id}` |
| 작업 목록 | `GET /api/jobs` — `limit`, `offset`, `status`, `search`, `client_id`, `batch_id`; 전체 건수는 `X-Total-Count` |
| 재시도·취소 | `POST /api/jobs/{id}/retry`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/retry` |
| 분석 이력·재분석 | `GET /api/contents/{content_id}/analyses?record_id=...`, `POST /api/contents/{content_id}/reanalyze?record_id=...` |
| 심사 | `POST /api/reviews/{content_id}?record_id=...` |
| 평가 | `PUT /api/evaluations/labels/{record_id}`, `GET /api/evaluations/summary`, `GET/POST /api/evaluations/datasets`, `GET/POST /api/evaluations/datasets/{id}/reports` |
| 정책 | `GET/PUT /api/policies/{client_id}`, `POST /api/policies/{client_id}/preview` |
| 대량 수집 | `POST /api/batches/preview`, `POST /api/batches`, `GET /api/batches`, `GET /api/batches/{id}/errors.csv` |
| 고객 상세·재시도 | `GET /auth/contents/{record_id}`, `POST /auth/contents/{record_id}/retry` |
| 운영 상태 | `GET /health`, `GET /ready`, `GET /api/operations` |

외부 `content_id`는 고객 안에서만 유일하다. 여러 고객이 같은 값을 사용할 수 있으므로 운영자 요청은 내부 `record_id`도 전달한다. 고객 데이터 접근 범위는 서버에서 제한하며 UI 필터만으로 격리하지 않는다.

웹훅 발송은 심사 상태·감사 이력과 같은 트랜잭션으로 예약한다. HMAC 서명, 영속 재시도, 이벤트 ID와 `review_version`을 사용한다. 수신자는 중복·역순을 처리해야 한다. 자세한 서명 계약은 `README.md`와 `demo-receiver/main.py`를 따른다.

## 6. 배포·DB·백업 인수인계

### 주소와 실행 환경

| 항목 | 주소 / 설정 |
|---|---|
| 대시보드 | `http://localhost:3003` |
| 백엔드 API 문서 | `http://localhost:8003/docs` |
| PostgreSQL 호스트 포트 | `127.0.0.1:5434` |
| Docker 내부 포트 | dashboard `3000`, backend `8000`, db `5432` |
| Compose 서비스 | `db`, `backend`, `dashboard`, `analysis-worker`, `webhook-worker` |
| 선택 실행 | `pgadmin`: tools 프로필, `demo-receiver`: demo 프로필 |

Windows + PowerShell 작업 환경이며 이전 Docker 운영 명령은 WSL Ubuntu에서 실행했다. WSL 경로는 `/mnt/c/Users/Laptop PC/Desktop/contentguard_ai`다. 호스트 포트를 맞추기 위해 Docker 내부 포트를 변경할 필요는 없다.

2026-10-05 마지막 확인 당시 backend·postgres는 healthy, dashboard와 두 worker는 실행 중이었다. Windows 재시작 후에는 가동 상태를 다시 확인한다. `scripts/start-wsl-runtime.ps1`은 숨겨진 WSL 프로세스로 실행을 유지하는 보조 도구이며, Windows 자동 시작 작업은 등록하지 않았다.

### 마이그레이션과 보존 결과

- 최신 마이그레이션: `backend/migrations/versions/e50a61c972bd_reliable_analysis_and_evaluation.py`
- revision: `d27f9e4056ac` → **`e50a61c972bd`**
- 분석 버전, 작업 소유 토큰, 배치 오류, worker heartbeat, 고정 평가 데이터셋·보고서를 추가한다.
- 기존 분석 이력에 버전을 부여하며 이력이 없는 과거 콘텐츠도 기준 버전을 갖는다.
- 백엔드 컨테이너 시작 시 `alembic upgrade head` 후 서버를 실행한다.
- SQLite와 격리 PostgreSQL에서 업그레이드·다운그레이드를 검증했다.
- 운영 반영 전후 기존 12개 테이블의 건수와 데이터 digest가 일치했다. 기존 콘텐츠 9건도 보존했다.
- 실제 분석·재분석 검증에 사용한 임시 콘텐츠는 삭제했고, 임시 PostgreSQL 검증 컨테이너도 정리했다.

### 백업과 근거 파일

| 경로 | 내용 / 주의점 |
|---|---|
| `backups/20261005T064526Z/contentguard.dump` | 배포 전 운영 DB 백업 |
| `backups/20261005T064526Z/environment.env` | 당시 환경 백업. 비밀정보 포함: 출력·공유·커밋 금지 |
| `.deployment/upgrade-state-20261005.json` | 전후 테이블 건수·digest, revision, 테스트 결과, 백업 및 이전 이미지 태그 |
| `.deployment/upgrade_20261005.py` | 백업·격리 DB 검증·마이그레이션 리허설·보존 확인 도구 |
| `.deployment/smoke_20261005.py` | 실제 큐 분석·재분석·오래된 심사 거절 및 임시 데이터 정리 검증 |
| `.deployment/browser_20261005.cjs` | 배포된 UI의 브라우저 검증. 결정된 API 응답 fixture를 사용 |
| `.deployment/qa-jobs.png`, `qa-evaluation.png`, `qa-customer.png` | 화면 확인 자료 |
| `.deployment/audit_20261004.py` | 수정 전 문제 재현용. 수정 후 전체 회귀 테스트를 대신하지 않음 |

기존 backend와 dashboard 이미지에는 `before-20261005t064526z` 태그를 남겼다. 이미지 태그만 되돌리는 것으로 DB 호환성이 보장되지는 않는다. 복구가 필요하면 현재 데이터를 별도로 백업하고 코드·스키마·백업의 조합을 확인한다. 운영 볼륨을 삭제하는 명령을 사용하지 않는다.

`.deployment/`와 `backups/`는 Git에서 제외되어 있다. 다른 PC에서 저장소만 clone하면 이 자료는 없다. 필요한 자료는 별도로 안전하게 전달하되 환경 백업을 공개 저장소에 포함하지 않는다. 날짜가 붙은 배포 스크립트에는 당시 환경을 가정한 동작이 있으므로 내용을 확인한 뒤 필요한 단계만 실행한다.

## 7. 완료한 검증과 범위

아래는 **2026-10-05 작업 기록**이다. 현재 시점에 자동으로 다시 통과했다는 의미는 아니다.

| 검증 | 결과 |
|---|---|
| PostgreSQL 백엔드 전체 테스트 | 260개 통과 |
| SQLite 백엔드 테스트 | 당시 259개 통과, PostgreSQL 전용 1개 건너뜀 |
| 프런트엔드 테스트 | 9개 통과 |
| TypeScript 검사 | 통과 |
| Windows 및 Docker Node 24 프로덕션 빌드 | 통과 |
| npm 보안 검사 | 당시 취약점 0건 |
| 브라우저 확인 | 주요 화면 5개, 페이지 오류 0건 |
| 실제 운영 큐 | 신규 분석·재분석 모두 첫 시도에 COMPLETED |
| 오래된 분석 버전 심사 | HTTP 409로 거절 |
| DB·Ollama·두 worker 상태 | 당시 정상 |
| 기존 운영 데이터 보존 | 기존 12개 테이블 비교 일치, 콘텐츠 9건 보존 |
| 변경 파일 공백 검사 | `git -c core.safecrlf=false diff --check` 통과 |

브라우저 검증은 배포된 화면에 API fixture를 연결하여 선택 재시도, 페이지 이동, 평가 비교, 오류 CSV, 고객 상세·재시도와 고객 작업 화면을 확인했다. 전체 브라우저 흐름을 실제 운영 API로 검증한 것으로 과장하지 않는다. 실제 API 분석·재분석은 별도 smoke 검증을 수행했다.

## 8. 다음 담당자의 시작 순서와 명령

1. 이 문서, `README.md`, `PROJECT_GUIDELINES.md`를 읽는다.
2. `git status --short`, `git diff --stat`, 필요한 파일의 diff를 확인한다. 신규 파일은 `git diff`에 나오지 않으므로 따로 읽는다.
3. 운영 점검이 필요한 요청이라면 먼저 포트·컨테이너·DB revision을 읽기 전용으로 확인한다. 문서 작업만 이어받는다면 재배포할 필요는 없다.
4. 새로 승인된 범위를 정하고 기존 변경을 보존하며 작업한다. 이미 완료한 기능을 처음부터 다시 만들지 않는다.
5. 코드 변경에 맞는 테스트를 실행한다. 운영 DB 변경 시 별도 백업·마이그레이션·데이터 보존 검증을 수행한다.

프로젝트 루트에서 변경 상태 확인:

```powershell
git status --short
git diff --stat
git -c core.safecrlf=false diff --check
```

WSL Docker 읽기 전용 확인 예시:

```powershell
wsl -d Ubuntu --cd "/mnt/c/Users/Laptop PC/Desktop/contentguard_ai" -- docker compose ps
wsl -d Ubuntu --cd "/mnt/c/Users/Laptop PC/Desktop/contentguard_ai" -- docker compose exec -T backend alembic current
Invoke-RestMethod -Uri 'http://localhost:8003/ready'
Invoke-RestMethod -Uri 'http://localhost:8003/health'
```

의존성이 준비된 Python 가상환경에서 백엔드 검사:

```powershell
# 프로젝트 루트에서 실행. TEST_DATABASE_URL 미지정 시 기본 SQLite 사용.
python -m pytest -q --tb=short
```

PostgreSQL 검증은 **폐기 가능한 별도 `contentguard_test` DB**를 만들고 `TEST_DATABASE_URL`로 연결한다. 테스트는 테이블을 생성·삭제하므로 운영 `contentguard_db`를 연결하면 안 된다. CI 설정을 참고하며 비밀정보를 명령 기록이나 문서에 남기지 않는다.

프런트엔드 검사:

```powershell
Set-Location dashboard
npm ci
npm test
npm run typecheck
npm run build
npm audit --audit-level=high
```

Docker 없이 개발 서버를 실행할 경우 대시보드는 `npm run dev`로 3003을 사용한다. 백엔드는 `backend` 폴더에서 `uvicorn main:app --host 0.0.0.0 --port 8003`로 실행하며 DB·LLM 설정이 필요하다. 비동기 분석과 웹훅을 사용하려면 두 worker도 각각 실행해야 한다. 이미 사용 중인 포트에 중복 실행하지 않는다.

PowerShell에서 한글 문서를 읽을 때 `Get-Content -Encoding UTF8`을 사용한다. 이번 확인에서 기본 인코딩으로 읽으면 출력이 깨졌지만 UTF-8로 읽은 원본 문서는 정상이었다.

## 9. 남은 개선 후보와 우선순위 제안

이 항목들은 완료된 기능과 구분되는 후속 후보다. 제품 요구사항과 운영 데이터를 확인한 뒤 범위를 정한다.

1. **실제 평가 정답 데이터 구축과 품질 측정**: 카테고리별 오탐·미탐, 인용·우회 표현, 개인정보 표현을 포함한 데이터를 만들고 고정 보고서로 공급자·모델·프롬프트를 비교한다. 현재 평가 기능만으로 정확도를 입증할 수 없다.
2. **처리량·지연 측정**: 큐와 동기 API의 실제 대기 시간, 처리 시간, 동시 요청 한계를 측정한 뒤 워커 확장·우선순위·고객별 자원 배분을 결정한다.
3. **요청 제한 개선**: 현재 IP 기반 메모리 rate limiter를 다중 프로세스 운영에 맞춰 계정별·공유 저장소 방식으로 확장한다.
4. **데이터 보존 정책**: 과거 원문, 분석 이력, 감사 이벤트, 웹훅 이력의 보존 기간과 정리 절차를 정한다. 기존 원문을 일괄 변경·삭제하는 작업은 아직 하지 않았다.
5. **운영 관측·알림 확대**: 현재 대시보드 경고를 바탕으로 필요한 외부 알림, 백업 복구 점검, Windows 재시작 후 자동 복구 여부를 검토한다. 외부 메시지 발송·자동 시작 등록은 별도 요구사항이 필요하다.
6. **의존성 재현성**: 프런트엔드 lockfile을 유지하고 Python 공급자 SDK·배포 이미지의 버전 관리와 정기 점검을 강화한다.

## 10. 다음 작업에서 지킬 핵심 조건

- 포트 3003/8003, 고객별 데이터 격리, 기존 데이터와 미커밋 변경을 보존한다.
- LLM 실패를 성공으로 표시하거나 AI 권장 조치를 최종 심사 결과로 자동 집행하지 않는다.
- 공통 분석 파이프라인을 라우터마다 복제하지 않는다.
- 심사의 두 버전 검증, 재심사 표시, 큐 소유권 확인과 원자적 저장을 유지한다.
- 평가 스냅샷을 나중의 재분석·정답 수정으로 덮어쓰지 않는다.
- 운영 `.env`, DB 백업, 토큰을 문서·로그·커밋에 노출하지 않는다.
- 실제 수행한 검증과 과거 기록, 모킹한 검증과 실제 운영 검증을 구분해 보고한다.

다음 세션 시작 시 전달할 문장 예시: **“프로젝트 루트의 claude.md와 PROJECT_GUIDELINES.md를 먼저 읽고, 미커밋 변경 및 3003/8003 포트를 보존하면서 새로 요청한 작업을 이어서 진행해줘.”**
