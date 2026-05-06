"""
Active Learning 후보 데이터 내보내기 스크립트
실행: python scripts/export_active_learning.py  (contentguard_ai/ 루트에서)

운영자 심사 결과 중 모델 예측과 불일치한 건을 training_data.csv에 추가한다.
추가 후 'python scripts/train.py'로 모델을 재학습하면 된다.
"""
import csv
import sys
from pathlib import Path

import requests

ROOT_DIR  = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "training_data.csv"
API_URL   = "http://localhost:8000/api/active-learning/candidates"


def load_existing_texts() -> set[str]:
    if not DATA_PATH.exists():
        return set()
    with open(DATA_PATH, encoding="utf-8") as f:
        return {row["text"] for row in csv.DictReader(f)}


def export(disagreement_only: bool = True) -> None:
    print(f"후보 데이터 조회 중 (disagreement_only={disagreement_only})...")
    res = requests.get(API_URL, params={"disagreement_only": str(disagreement_only).lower()})
    res.raise_for_status()
    candidates = res.json()

    if not candidates:
        print("내보낼 후보 데이터가 없습니다. 운영자 심사가 완료된 건이 있는지 확인하세요.")
        return

    existing_texts = load_existing_texts()
    new_rows = [c for c in candidates if c["text"] not in existing_texts]

    print(f"전체 후보: {len(candidates)}건  /  신규(중복 제외): {len(new_rows)}건")

    if not new_rows:
        print("모든 후보가 이미 학습 데이터에 포함되어 있습니다.")
        return

    with open(DATA_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "score"])
        for row in new_rows:
            writer.writerow({"text": row["text"], "score": row["suggested_score"]})

    print(f"\n{len(new_rows)}건 추가 완료 → {DATA_PATH}")
    print("다음 단계: python scripts/train.py")


if __name__ == "__main__":
    # --all 플래그로 불일치 건 외 전체 심사 완료 건도 포함 가능
    disagreement_only = "--all" not in sys.argv
    export(disagreement_only=disagreement_only)
