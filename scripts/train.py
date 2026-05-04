"""
모델 학습 스크립트 — 회귀 기반 risk_score 예측
실행: python scripts/train.py  (contentguard_ai/ 루트에서)
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

DATA_PATH = ROOT_DIR / "data" / "training_data.csv"
MODELS_DIR = ROOT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)


def score_to_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.60:
        return "HIGH"
    if score >= 0.30:
        return "MEDIUM"
    return "LOW"


def evaluate_level_accuracy(y_true: np.ndarray, y_pred: np.ndarray):
    true_levels = [score_to_level(s) for s in y_true]
    pred_levels = [score_to_level(s) for s in y_pred]
    correct = sum(t == p for t, p in zip(true_levels, pred_levels))
    print(f"\n[등급 분류 정확도] {correct}/{len(true_levels)} = {correct/len(true_levels):.1%}")

    for level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        indices = [i for i, l in enumerate(true_levels) if l == level]
        if not indices:
            continue
        level_correct = sum(true_levels[i] == pred_levels[i] for i in indices)
        print(f"  {level:8s}: {level_correct}/{len(indices)} 정확")


def train():
    df = pd.read_csv(DATA_PATH)
    print(f"데이터 로드: {len(df)}개")
    print(f"점수 분포 — min: {df['score'].min():.2f}  max: {df['score'].max():.2f}  mean: {df['score'].mean():.2f}")

    texts = df["text"].tolist()
    scores = df["score"].tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        texts, scores, test_size=0.2, random_state=42
    )

    # char n-gram + word n-gram 동시 사용 → 한국어 일반화 성능 향상
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        max_features=15000,
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = Ridge(alpha=1.0)
    model.fit(X_train_vec, y_train)

    y_pred = np.clip(model.predict(X_test_vec), 0.0, 1.0)

    print(f"\n[회귀 성능]")
    print(f"  MAE : {mean_absolute_error(y_test, y_pred):.4f}")
    print(f"  R²  : {r2_score(y_test, y_pred):.4f}")

    evaluate_level_accuracy(np.array(y_test), y_pred)

    joblib.dump(vectorizer, MODELS_DIR / "tfidf_vectorizer.pkl")
    joblib.dump(model, MODELS_DIR / "ridge_model.pkl")
    print(f"\n모델 저장 완료 → {MODELS_DIR}")


if __name__ == "__main__":
    train()
