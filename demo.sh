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

# 랜덤 샘플 텍스트
TEXTS=(
  # 사기 / 먹튀
  "이 판매자 완전 사기꾼이에요. 환불도 안 해주고 연락도 안 됨."
  "결제했는데 일주일째 배송도 없고 연락도 두절. 먹튀 당한 것 같아요."
  "강제로 정기결제 됐는데 해지도 안 되고 고객센터도 없음. 사기입니다."
  "입금하고 나서 판매자가 잠수탔어요. 경찰 신고했습니다."
  "중고나라에서 산 건데 받자마자 막혀버린 계정이라 로그인도 안 됨. 완전 사기."
  "이벤트 당첨됐다고 개인정보 입력하라더니 연락 끊김. 피싱 사이트입니다."

  # 가품 / 허위광고
  "가품 팔면서 정품이라고 우기는 거 진짜 황당하네요. 신고합니다."
  "광고랑 실물이 완전 달라요. 이건 명백한 허위광고 아닌가요?"
  "정품 인증서 첨부했다고 해서 믿었는데 완전 위조였음. 고발 예정."
  "명품백이라고 팔아놓고 뚜껑 열어보니 짝퉁. 환불도 거절함."
  "성분표에 없는 성분이 들어있고 원산지도 거짓말. 식약처 신고함."
  "AS 1년 보장이라더니 접수하니까 해당 없다고 함. 완전 거짓말."

  # 개인정보 / 스팸
  "개인정보 팔아먹는 업체 같음. 가입했더니 스팸 문자가 폭발적으로 옴."
  "탈퇴했는데도 계속 마케팅 문자 옴. 개인정보 삭제 요청해도 무시함."
  "회원가입만 했는데 다음날부터 대출 광고 전화가 쏟아짐. 개인정보 판 거 맞죠?"
  "앱 설치했더니 연락처 전체를 무단으로 수집한 정황 있음. 즉시 삭제 요망."

  # 후기 조작 / 어뷰징
  "후기 조작 의심됩니다. 별점 5개짜리 리뷰가 전부 같은 날 올라왔어요."
  "리뷰 작성하면 현금 준다고 해서 다들 5점 주는 거 다 알면서 왜 방치함?"
  "경쟁사 제품 후기에 조직적으로 1점 테러하는 거 발각됐는데 제재가 없네요."
  "체험단인 척 후기 올리는 알바 계정들 다 같은 문체임. 플랫폼이 방치 중."

  # 폭언 / 욕설
  "이딴 쓰레기 같은 서비스를 돈 받고 파냐. 진짜 역겹다."
  "고객센터 직원이 반말로 응대했습니다. 녹음본 있고 법적 대응 검토 중."
  "배송 늦는다고 따졌더니 담당자가 욕설을 함. 이게 말이 되냐."

  # 위험 정보 유포
  "이 약이랑 저 약 같이 먹으면 살 빠진다는 글 계속 올라오는데 사실이에요?"
  "다이어트 약이라고 판매하는데 성분 보니까 식욕억제제 불법 혼합 의심됨."
  "미성년자한테도 주류 판매하는 업체인데 신고해도 계속 영업 중."

  # 정상 (낮은 위험)
  "배송이 예상보다 하루 늦었지만 제품 상태는 양호했습니다."
  "포장이 조금 구겨져서 왔는데 내용물 이상 없어서 그냥 쓰려고요."
  "사이즈가 생각보다 작게 나왔어요. 반품 절차 좀 알 수 있을까요?"
  "색상이 화면이랑 약간 달라요. 그래도 퀄리티는 나쁘지 않네요."
)
IDX=$(( RANDOM % ${#TEXTS[@]} ))
SAMPLE_TEXT="${TEXTS[$IDX]}"

# JSON 내 UTC 타임스탬프를 KST(+09:00)로 변환해서 출력
# heredoc + pipe는 stdin 충돌로 동작 안 함 → 임시 파일로 스크립트 전달
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
echo " ContentGuard AI — 웹훅 데모"
echo "======================================"
echo ""

# 1. 콘텐츠 제출
echo "[1/3] 콘텐츠 제출 (content_id: $CONTENT_ID)"
echo "      텍스트: $SAMPLE_TEXT"
echo ""
RESULT=$(curl -s -X POST "$BASE_URL/api/analyze" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEMO_CLIENT_API_KEY" \
  -d "{\"content_id\": \"$CONTENT_ID\", \"text\": \"$SAMPLE_TEXT\"}")

echo "$RESULT" | pretty_kst
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
curl -s "$RECEIVER_URL/logs" | pretty_kst
echo ""
echo "======================================"
echo " 데모 완료"
echo "======================================"
