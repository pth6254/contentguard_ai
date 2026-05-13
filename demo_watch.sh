#!/bin/bash
# 웹훅 데모 — 상시 감시
#
# 사용법: bash demo_watch.sh  (항상 켜두기)
#
# 자동으로 표시하는 두 가지 이벤트:
#   1. demo_submit.sh 제출 후 AI 분석 완료 (SUBMITTED → PENDING)
#   2. 대시보드 심사 완료 후 웹훅 수신 (PENDING → 심사결과)

source .env 2>/dev/null || true

RECEIVER_URL="http://localhost:9000"

_KST_PY=$(mktemp /tmp/pretty_kst_XXXXXX.py)
NOTIFIED_PENDING=$(mktemp /tmp/demo_notified_pending_XXXXXX)
NOTIFIED_DONE=$(mktemp /tmp/demo_notified_done_XXXXXX)
trap "rm -f $_KST_PY $NOTIFIED_PENDING $NOTIFIED_DONE" EXIT

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
echo " ContentGuard AI — 데모 감시 중"
echo " Ctrl+C 로 종료"
echo "======================================"
echo ""
echo "  감시 이벤트:"
echo "    [분석완료] demo_submit.sh 제출 후 AI 분석 결과"
echo "    [심사완료] 대시보드 심사 후 웹훅 수신 결과"
echo ""
echo "  대시보드: http://localhost:3000/queue"
echo ""

TICK=0
while true; do
  REVIEWS=$(curl -s "$RECEIVER_URL/reviews" 2>/dev/null)

  # 각 리뷰 상태별 처리
  echo "$REVIEWS" | python3 -c "
import sys, json
try:
    for r in json.load(sys.stdin):
        print(r['content_id'], r.get('status', ''))
except:
    pass
" 2>/dev/null | while IFS=' ' read -r CID STATUS; do
    [ -z "$CID" ] && continue

    # 이벤트 1: SUBMITTED → PENDING (AI 분석 완료)
    if [ "$STATUS" = "PENDING" ] && ! grep -qx "$CID" "$NOTIFIED_PENDING" 2>/dev/null; then
      echo "$CID" >> "$NOTIFIED_PENDING"
      DETAIL=$(curl -s "$RECEIVER_URL/reviews/$CID" 2>/dev/null)
      echo ""
      echo "────────────────────────────────────────"
      echo " [AI 분석 완료] $CID"
      echo "────────────────────────────────────────"
      echo "$DETAIL" | pretty_kst
      echo ""
      echo "  → 대시보드에서 심사하세요: http://localhost:3000/queue"
      echo ""
    fi

    # 이벤트 2: PENDING → 심사결과 (웹훅 수신)
    if [ "$STATUS" != "SUBMITTED" ] && [ "$STATUS" != "PENDING" ] && [ -n "$STATUS" ] \
       && ! grep -qx "$CID" "$NOTIFIED_DONE" 2>/dev/null; then
      echo "$CID" >> "$NOTIFIED_DONE"
      DETAIL=$(curl -s "$RECEIVER_URL/reviews/$CID" 2>/dev/null)
      echo ""
      echo "────────────────────────────────────────"
      echo " [웹훅 수신] 심사 결과 → 데모 DB 반영"
      echo "────────────────────────────────────────"
      echo "$DETAIL" | pretty_kst
      echo ""
    fi
  done

  TICK=$(( TICK + 3 ))
  echo -ne "  감시 중... ${TICK}초 (Ctrl+C 로 종료)\r"
  sleep 3
done
