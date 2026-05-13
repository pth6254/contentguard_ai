#!/bin/bash
# 웹훅 데모 — Phase 1: 리뷰 제출 + AI 분석 결과 확인
#
# 사전 준비:
#   1. docker-compose up -d
#   2. .env의 DEMO_CLIENT_API_KEY에 발급받은 키 입력
#   3. 어드민 페이지에서 해당 클라이언트의 webhook_url 등록
#      → http://demo-receiver:9000/webhook
#
# 사용 흐름:
#   1. bash demo.sh          → 텍스트 제출, AI 분석 결과 확인
#   2. 대시보드에서 심사      → http://localhost:3000/queue
#   3. bash demo_watch.sh    → 웹훅 수신 + 데모 DB 반영 결과 자동 표시

set -e
source .env

BASE_URL="http://localhost:8000"
RECEIVER_URL="http://localhost:9000"

_KST_PY=$(mktemp /tmp/pretty_kst_XXXXXX.py)
trap "rm -f $_KST_PY" EXIT
cat > "$_KST_PY" << 'PYEOF'
import sys, json, re
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ISO_RE = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))')

def to_kst(m):
    s = m.group(1).replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s).astimezone(KST)
        return dt.strftime('%Y-%m-%d %H:%M:%S KST')
    except Exception:
        return m.group(1)

raw = sys.stdin.read()
try:
    obj = json.loads(raw)
    pretty = json.dumps(obj, ensure_ascii=False, indent=2)
except Exception:
    pretty = raw
print(ISO_RE.sub(to_kst, pretty))
PYEOF

pretty_kst() {
  python3 "$_KST_PY"
}

echo "======================================"
echo " ContentGuard AI — 웹훅 데모 (제출)"
echo " Ctrl+C 로 종료"
echo "======================================"
echo ""

ROUND=1

while true; do
  echo "── Round $ROUND ──────────────────────────"
  echo ""
  read -p "분석할 텍스트를 입력하세요: " SAMPLE_TEXT
  echo ""

  # 1. 데모 DB에 리뷰 제출 → ContentGuard 분석 백그라운드 시작
  echo "[1/2] 리뷰 제출 (데모 DB 저장 + ContentGuard 분석 요청)"
  echo "      텍스트: $SAMPLE_TEXT"
  echo ""
  RESULT=$(curl -s -X POST "$RECEIVER_URL/reviews" \
    -H "Content-Type: application/json" \
    -d "{\"text\": \"$SAMPLE_TEXT\"}")

  CONTENT_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['content_id'])" 2>/dev/null || echo "?")

  echo "      → content_id : $CONTENT_ID"
  echo "      → AI 분석 진행 중..."
  echo ""

  # ContentGuard 분석 완료 대기 (SUBMITTED → PENDING)
  for i in $(seq 1 30); do
    STATUS=$(curl -s "$RECEIVER_URL/reviews/$CONTENT_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null)
    if [ "$STATUS" = "PENDING" ]; then
      break
    fi
    echo -ne "      분석 대기 중... ${i}초\r"
    sleep 3
  done
  echo ""

  RISK_LEVEL=$(curl -s "$RECEIVER_URL/reviews/$CONTENT_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('risk_level','UNKNOWN'))" 2>/dev/null)
  echo "      → 위험 등급  : $RISK_LEVEL"
  echo ""
  echo "  [데모 DB 현재 상태]"
  curl -s "$RECEIVER_URL/reviews/$CONTENT_ID" | pretty_kst
  echo ""

  # content_id 저장 — demo_watch.sh가 읽어서 심사 결과 감시
  echo "$CONTENT_ID" > .demo_last_id

  # 2. 심사 안내
  echo "[2/2] 대시보드에서 '$CONTENT_ID' 콘텐츠를 심사하세요."
  echo "      http://localhost:3000/queue"
  echo ""
  echo "      심사 완료 시 웹훅이 자동으로 데모 DB에 반영됩니다."
  echo "      결과 확인: bash demo_watch.sh"
  echo ""
  echo "══════════════════════════════════════════"
  echo ""

  ROUND=$(( ROUND + 1 ))
done
