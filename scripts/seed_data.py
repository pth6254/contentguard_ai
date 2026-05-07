"""
대시보드 테스트용 시드 데이터 전송 스크립트
실행: python scripts/seed_data.py  (백엔드가 실행 중이어야 합니다)

옵션:
  --url   백엔드 주소 (기본: http://localhost:8000)
  --delay 요청 간격(초) (기본: 0.3)
"""
import argparse
import time
import urllib.request
import urllib.error
import json

SAMPLES = [
    # LOW
    ("SEED_LOW_001", "배송이 빠르고 제품 품질도 만족스러워요"),
    ("SEED_LOW_002", "포장이 꼼꼼해서 파손 없이 잘 받았습니다"),
    ("SEED_LOW_003", "가격 대비 품질이 매우 좋아요 재구매 예정입니다"),
    ("SEED_LOW_004", "친절한 응대 감사합니다 잘 쓸게요"),
    ("SEED_LOW_005", "사진과 동일한 색상으로 왔어요 만족합니다"),
    # MEDIUM
    ("SEED_MED_001", "배송이 좀 늦었지만 제품 자체는 괜찮아요"),
    ("SEED_MED_002", "설명과 조금 다른 부분이 있어 아쉬웠어요"),
    ("SEED_MED_003", "환불 정책이 불명확해서 불편했습니다"),
    ("SEED_MED_004", "실제 효능이 광고만큼은 아닌 것 같아요"),
    ("SEED_MED_005", "구매 후 연락이 잘 안 되는 업체입니다"),
    # HIGH
    ("SEED_HIGH_001", "너 집 주소 알고 있어 조심하는 게 좋을 거야"),
    ("SEED_HIGH_002", "이거 안 들어주면 개인정보 온라인에 다 올린다"),
    ("SEED_HIGH_003", "직접 찾아가겠다는 협박성 메시지를 받았습니다"),
    ("SEED_HIGH_004", "불법 도박 사이트로 유도하는 게시물입니다"),
    ("SEED_HIGH_005", "미성년자를 대상으로 한 부적절한 접근 시도"),
    # CRITICAL
    ("SEED_CRI_001", "투자하면 원금 보장에 수익 300% 보장 지금 바로 입금하세요"),
    ("SEED_CRI_002", "가짜 쇼핑몰 결제 유도 및 개인정보 탈취 피싱 사이트"),
    ("SEED_CRI_003", "불법 의약품 판매 및 처방전 없이 마약류 구매 가능"),
    ("SEED_CRI_004", "해킹 도구 및 악성코드 판매 다크웹 링크 공유"),
    ("SEED_CRI_005", "아동 대상 불법 콘텐츠 제작 및 유포 게시물"),
]


def analyze(base_url: str, content_id: str, text: str) -> dict:
    payload = json.dumps({"content_id": content_id, "text": text}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/analyze",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",   default="http://localhost:8000")
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    print(f"백엔드: {args.url}")
    print(f"전송 건수: {len(SAMPLES)}개\n")

    ok = err = 0
    for content_id, text in SAMPLES:
        try:
            result = analyze(args.url, content_id, text)
            level = result.get("risk_level", "?")
            score = result.get("risk_score", 0)
            print(f"  [{level:8s}] {score:.2f}  {content_id}  {text[:30]}")
            ok += 1
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"  [ERROR {e.code}] {content_id}: {body[:80]}")
            err += 1
        except Exception as e:
            print(f"  [ERROR] {content_id}: {e}")
            err += 1
        time.sleep(args.delay)

    print(f"\n완료: 성공 {ok}건 / 실패 {err}건")


if __name__ == "__main__":
    main()
