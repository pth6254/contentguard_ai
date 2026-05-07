"""
시연용 크롤링 → ContentGuard 분석 파이프라인

실행 예시:
  python scripts/demo_crawl.py --url "https://example.com/board/1234"

필요한 환경변수 (.env):
  FIRECRAWL_API_KEY  Firecrawl API 키
  OLLAMA_BASE_URL    Ollama 주소 (기본: http://localhost:11434)
  OLLAMA_MODEL       Ollama 모델 (기본: qwen3.5:9b)
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import ollama
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL      = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

LEVEL_COLOR = {"LOW": "\033[32m", "MEDIUM": "\033[33m", "HIGH": "\033[31m", "CRITICAL": "\033[35m"}
RESET = "\033[0m"


# ── 1. Firecrawl 스크래핑 ──────────────────────────────────────────────────

def scrape(url: str) -> str:
    resp = requests.post(
        "https://api.firecrawl.dev/v1/scrape",
        headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
        json={"url": url, "formats": ["markdown"]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl 실패: {data}")
    return data["data"]["markdown"]


# ── 2. Ollama로 텍스트 추출 ────────────────────────────────────────────────

def extract_texts(markdown: str, max_items: int) -> list[str]:
    client = ollama.Client(host=OLLAMA_BASE_URL)
    prompt = f"""다음은 웹페이지를 마크다운으로 변환한 내용입니다.
사용자가 직접 작성한 댓글, 리뷰, 게시글 본문만 추출하세요.
메뉴, 광고, 버튼, 날짜, 작성자명 등 부가 정보는 제외하세요.
최대 {max_items}개를 JSON 문자열 배열로만 반환하세요. 설명 없이 배열만 출력하세요.

출력 형식:
["텍스트1", "텍스트2", "텍스트3"]

마크다운:
{markdown[:6000]}"""

    response = client.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )
    content = response["message"]["content"].strip()

    start = content.find("[")
    end   = content.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"JSON 배열을 찾을 수 없습니다:\n{content[:300]}")
    return json.loads(content[start:end])


# ── 3. ContentGuard 분석 요청 ──────────────────────────────────────────────

def analyze(base_url: str, content_id: str, text: str) -> dict:
    resp = requests.post(
        f"{base_url}/api/analyze",
        json={"content_id": content_id, "text": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── 메인 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="크롤링 → ContentGuard 분석 시연 스크립트")
    parser.add_argument("--url",          required=True,              help="크롤링할 페이지 URL")
    parser.add_argument("--contentguard", default="http://localhost:8000", help="ContentGuard API 주소")
    parser.add_argument("--max",          type=int,   default=20,     help="최대 추출 건수 (기본 20)")
    parser.add_argument("--delay",        type=float, default=0.5,    help="요청 간격 초 (기본 0.5)")
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        print("오류: .env에 FIRECRAWL_API_KEY가 없습니다.")
        sys.exit(1)

    # 1단계: 스크래핑
    print(f"\n[1] 페이지 스크래핑 중...")
    print(f"    URL: {args.url}")
    try:
        markdown = scrape(args.url)
    except Exception as e:
        print(f"    실패: {e}")
        sys.exit(1)
    print(f"    완료: {len(markdown):,}자 수신\n")

    # 2단계: 텍스트 추출
    print(f"[2] Ollama({OLLAMA_MODEL})로 사용자 텍스트 추출 중...")
    try:
        texts = extract_texts(markdown, args.max)
    except Exception as e:
        print(f"    실패: {e}")
        sys.exit(1)
    print(f"    완료: {len(texts)}개 추출\n")

    if not texts:
        print("추출된 텍스트가 없습니다. URL을 확인하세요.")
        sys.exit(0)

    # 3단계: ContentGuard 분석
    print(f"[3] ContentGuard 분석 시작 ({len(texts)}건)\n")
    print(f"    {'등급':10s} {'점수':6s}  텍스트")
    print(f"    {'─'*60}")

    ok = err = 0
    prefix = f"DEMO_{int(time.time())}"

    for i, text in enumerate(texts, start=1):
        content_id = f"{prefix}_{i:03d}"
        try:
            result = analyze(args.contentguard, content_id, text)
            level  = result.get("risk_level", "?")
            score  = result.get("risk_score", 0)
            color  = LEVEL_COLOR.get(level, "")
            print(f"    {color}[{level:8s}]{RESET} {score:.2f}  {text[:45]}")
            ok += 1
        except requests.HTTPError as e:
            detail = e.response.json().get("detail", e.response.text)[:60]
            print(f"    [ERROR {e.response.status_code}] {text[:35]}... → {detail}")
            err += 1
        except Exception as e:
            print(f"    [ERROR] {text[:35]}... → {e}")
            err += 1
        time.sleep(args.delay)

    print(f"\n    {'─'*60}")
    print(f"    완료: 성공 {ok}건 / 실패 {err}건")
    print(f"    대시보드: {args.contentguard.replace('8000', '3000')}\n")


if __name__ == "__main__":
    main()
