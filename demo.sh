#!/bin/bash
# 웹훅 데모 스크립트
# 사전 준비:
#   1. docker-compose up -d
#   2. .env의 DEMO_CLIENT_API_KEY에 발급받은 키 입력
#   3. 어드민 페이지에서 해당 클라이언트의 webhook_url 등록
#      → http://demo-receiver:9000/webhook

set -e
source .env

BASE_URL="http://localhost:8000"
RECEIVER_URL="http://localhost:9000"
CONTENT_ID="demo-$(date +%s)"

echo "======================================"
echo " ContentGuard AI — 웹훅 데모"
echo "======================================"
echo ""

# 1. 콘텐츠 제출
echo "[1/3] 콘텐츠 제출 (content_id: $CONTENT_ID)"
RESULT=$(curl -s -X POST "$BASE_URL/api/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEMO_CLIENT_API_KEY" \
  -d "{\"content_id\": \"$CONTENT_ID\", \"text\": \"이 판매자 완전 사기꾼이에요. 환불도 안 해주고 연락도 안 됨.\"}")

echo "$RESULT" | python3 -m json.tool
echo ""

RISK_LEVEL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['risk_level'])" 2>/dev/null || echo "?")
echo "→ 위험 등급: $RISK_LEVEL"
echo ""

# 2. 대시보드에서 심사하도록 안내
echo "[2/3] 대시보드 심사 큐에서 '$CONTENT_ID' 콘텐츠를 심사하세요."
echo "      http://localhost:3000/queue"
echo ""
read -p "      심사 완료 후 Enter를 누르세요..."
echo ""

# 3. 웹훅 수신 확인
echo "[3/3] 웹훅 수신 로그 확인"
curl -s "$RECEIVER_URL/logs" | python3 -m json.tool
echo ""
echo "======================================"
echo " 데모 완료"
echo "======================================"
