"""
모델 학습 스크립트
실행: python scripts/train.py  (contentguard_ai/ 루트에서)

새 모델 추가 방법:
  1. BaseTrainer를 상속한 클래스 작성
  2. TRAINERS 리스트에 인스턴스 추가
  → train() 함수는 건드리지 않아도 됨
"""
import sys
from abc import ABC, abstractmethod
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import classification_report, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVR

DATA_PATH  = ROOT_DIR / "data" / "training_data.csv"
MODELS_DIR = ROOT_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

LEVEL_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def score_to_level(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.60:
        return "HIGH"
    if score >= 0.30:
        return "MEDIUM"
    return "LOW"


# ──────────────────────────────────────────────
# 공통 리포트 유틸
# ──────────────────────────────────────────────

def report_regression(name: str, y_true: np.ndarray, y_pred: np.ndarray) -> None:
    y_pred = np.clip(y_pred, 0.0, 1.0)
    mae = mean_absolute_error(y_true, y_pred)
    r2  = r2_score(y_true, y_pred)

    true_levels = [score_to_level(s) for s in y_true]
    pred_levels = [score_to_level(s) for s in y_pred]
    acc = sum(t == p for t, p in zip(true_levels, pred_levels)) / len(true_levels)
    f1  = f1_score(true_levels, pred_levels, labels=LEVEL_ORDER, average="macro", zero_division=0)

    print(f"\n{'─'*44}")
    print(f"  {name}")
    print(f"  MAE: {mae:.4f}   R²: {r2:.4f}   등급 정확도: {acc:.1%}   F1(macro): {f1:.1%}")
    print(classification_report(true_levels, pred_levels, labels=LEVEL_ORDER, zero_division=0))


def report_classifier(name: str, y_true: list[str], y_pred: list[str]) -> None:
    acc = sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true)
    f1  = f1_score(y_true, y_pred, labels=LEVEL_ORDER, average="macro", zero_division=0)

    print(f"\n{'─'*44}")
    print(f"  {name}")
    print(f"  등급 정확도: {acc:.1%}   F1(macro): {f1:.1%}")
    print(classification_report(y_true, y_pred, labels=LEVEL_ORDER, zero_division=0))


# ──────────────────────────────────────────────
# Trainer 인터페이스
# ──────────────────────────────────────────────

class BaseTrainer(ABC):
    """
    새 모델을 추가하려면 이 클래스를 상속하고
    fit / evaluate / save 를 구현한 뒤 TRAINERS에 등록한다.
    """
    model_name: str  # 로그/출력용 이름
    save_file: str   # MODELS_DIR 아래 저장될 파일명

    @abstractmethod
    def fit(
        self,
        X_train,
        y_train_score: np.ndarray,
        y_train_level: list[str],
    ) -> None: ...

    @abstractmethod
    def evaluate(
        self,
        X_test,
        y_test_score: np.ndarray,
        y_test_level: list[str],
    ) -> None: ...

    def save(self) -> None:
        joblib.dump(self.model, MODELS_DIR / self.save_file)
        print(f"  저장: {self.save_file}")


# ──────────────────────────────────────────────
# 개별 Trainer 구현
# ──────────────────────────────────────────────

class RidgeTrainer(BaseTrainer):
    model_name = "Ridge Regression  →  ridge_model.pkl"
    save_file  = "ridge_model.pkl"

    def fit(self, X_train, y_train_score, y_train_level):
        self.model = Ridge(alpha=1.0)
        self.model.fit(X_train, y_train_score)

    def evaluate(self, X_test, y_test_score, y_test_level):
        report_regression(self.model_name, y_test_score, self.model.predict(X_test))


class LinearSVMTrainer(BaseTrainer):
    model_name = "Linear SVM (SVR)  →  linear_svm_model.pkl"
    save_file  = "linear_svm_model.pkl"

    def fit(self, X_train, y_train_score, y_train_level):
        self.model = LinearSVR(C=1.0, max_iter=2000, random_state=42)
        self.model.fit(X_train, y_train_score)

    def evaluate(self, X_test, y_test_score, y_test_level):
        report_regression(self.model_name, y_test_score, self.model.predict(X_test))


class LogisticRegressionTrainer(BaseTrainer):
    model_name = "Logistic Regression  →  logistic_regression_model.pkl"
    save_file  = "logistic_regression_model.pkl"

    def fit(self, X_train, y_train_score, y_train_level):
        self.model = LogisticRegression(
            C=1.0, max_iter=1000, random_state=42, class_weight="balanced"
        )
        self.model.fit(X_train, y_train_level)

    def evaluate(self, X_test, y_test_score, y_test_level):
        report_classifier(
            self.model_name, y_test_level, self.model.predict(X_test).tolist()
        )


# ──────────────────────────────────────────────
# 등록 — 새 모델은 여기에만 한 줄 추가
# ──────────────────────────────────────────────

TRAINERS: list[BaseTrainer] = [
    RidgeTrainer(),
    LinearSVMTrainer(),
    LogisticRegressionTrainer(),
]


# ──────────────────────────────────────────────
# 메인 학습 루프 — 수정 불필요
# ──────────────────────────────────────────────

def train():
    df = pd.read_csv(DATA_PATH)
    print(f"데이터 로드: {len(df)}개")
    print(f"점수 분포 — min: {df['score'].min():.2f}  max: {df['score'].max():.2f}  mean: {df['score'].mean():.2f}")

    texts  = df["text"].tolist()
    scores = df["score"].tolist()
    levels = [score_to_level(s) for s in scores]

    combined = list(zip(texts, scores, levels))
    train_data, test_data = train_test_split(combined, test_size=0.2, random_state=42)

    X_train_txt   = [d[0] for d in train_data]
    X_test_txt    = [d[0] for d in test_data]
    y_train_score = np.array([d[1] for d in train_data])
    y_test_score  = np.array([d[1] for d in test_data])
    y_train_level = [d[2] for d in train_data]
    y_test_level  = [d[2] for d in test_data]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 4), max_features=15000, sublinear_tf=True,
    )
    X_train = vectorizer.fit_transform(X_train_txt)
    X_test  = vectorizer.transform(X_test_txt)

    print(f"\n===== 모델 학습 ({len(TRAINERS)}개) =====")
    for trainer in TRAINERS:
        trainer.fit(X_train, y_train_score, y_train_level)
        trainer.evaluate(X_test, y_test_score, y_test_level)

    print(f"\n{'─'*44}")
    print("모델 저장")
    joblib.dump(vectorizer, MODELS_DIR / "tfidf_vectorizer.pkl")
    print("  저장: tfidf_vectorizer.pkl")
    for trainer in TRAINERS:
        trainer.save()


if __name__ == "__main__":
    train()
