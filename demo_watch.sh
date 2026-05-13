#!/bin/bash
# 웹훅 데모 — Phase 2: 심사 결과 자동 감지
#
# 사용법:
#   bash demo_watch.sh                  # .demo_last_id 파일에서 content_id 자동 로드
#   bash demo_watch.sh review-20260513  # content_id 직접 지정

source .env 2>/dev/null || true

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

# content_id 결정: 인자 > .demo_last_id 파일
CONTENT_ID="${1:-}"
if [ -z "$CONTENT_ID" ]; then
  if [ -f .demo_last_id ]; then
    CONTENT_ID=$(cat .demo_last_id)
  else
    echo "오류: content_id를 찾을 수 없습니다."
    echo "      demo.sh를 먼저 실행하거나, content_id를 인자로 전달하세요."
    echo "      예: bash demo_watch.sh review-20260513"
    exit 1
  fi
fi

echo "======================================"
echo " ContentGuard AI — 웹훅 데모 (심사 감시)"
echo "======================================"
echo ""
echo "  대상 content_id : $CONTENT_ID"
echo "  대시보드에서 심사하세요: http://localhost:3000/queue"
echo ""
echo "  운영자가 심사를 완료하면 ContentGuard가 웹훅을 발송하고,"
echo "  데모 DB에 즉시 반영된 결과를 여기서 자동으로 표시합니다."
echo ""

for i in $(seq 1 100); do
  RESPONSE=$(curl -s "$RECEIVER_URL/reviews/$CONTENT_ID" 2>/dev/null)
  REVIEW_STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('review_status') or '')" 2>/dev/null)

  if [ -n "$REVIEW_STATUS" ] && [ "$REVIEW_STATUS" != "PENDING" ]; then
    echo ""
    echo "======================================"
    echo " 웹훅 수신 완료 — 데모 DB 반영 결과"
    echo "======================================"
    echo ""
    echo "$RESPONSE" | pretty_kst
    echo ""
    exit 0
  fi

  echo -ne "  대기 중... ${i}초 (Ctrl+C 로 중단)\r"
  sleep 3
done

echo ""
echo "타임아웃: 5분 내 심사가 완료되지 않았습니다."
exit 1
