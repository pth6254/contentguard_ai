import pytest
from unittest.mock import patch

from config import settings
from services.prediction_service import ModelRegistry, _compute_confidence


class _MockModel:
    def __init__(self, name, score, level, action, is_primary=False):
        self.name = name
        self.version = "v1.0.0"
        self.model_type = "test"
        self.is_primary = is_primary
        self._score = score
        self._level = level
        self._action = action

    def predict(self, text: str) -> dict:
        return {
            "risk_score": self._score,
            "risk_level": self._level,
            "recommended_action": self._action,
            "confidence": 0.8,
            "latency_ms": 5,
        }

    def as_metadata(self) -> dict:
        return {
            "model_name": self.name,
            "model_version": self.version,
            "model_type": self.model_type,
        }


def _make_registry():
    registry = ModelRegistry()
    registry.register(_MockModel("model_a", 0.20, "LOW", "APPROVE", is_primary=True))
    registry.register(_MockModel("model_b", 0.70, "HIGH", "REVIEW"))
    registry.register(_MockModel("model_c", 0.50, "MEDIUM", "MONITOR"))
    return registry


def _make_predictions():
    return [
        {
            "model_name": "model_a", "risk_score": 0.20, "risk_level": "LOW",
            "recommended_action": "APPROVE", "confidence": 0.8, "latency_ms": 5,
            "is_selected": True, "is_shadow": False,
        },
        {
            "model_name": "model_b", "risk_score": 0.70, "risk_level": "HIGH",
            "recommended_action": "REVIEW", "confidence": 0.8, "latency_ms": 5,
            "is_selected": False, "is_shadow": True,
        },
        {
            "model_name": "model_c", "risk_score": 0.50, "risk_level": "MEDIUM",
            "recommended_action": "MONITOR", "confidence": 0.8, "latency_ms": 5,
            "is_selected": False, "is_shadow": True,
        },
    ]


class TestComputeConfidence:
    @pytest.mark.parametrize("score", [0.30, 0.60, 0.85])
    def test_at_boundary_returns_zero(self, score):
        assert _compute_confidence(score) == 0.0

    @pytest.mark.parametrize("score", [0.00, 0.15, 1.00])
    def test_far_from_boundary_returns_one(self, score):
        assert _compute_confidence(score) == 1.0

    def test_midpoint_between_boundaries(self):
        # score=0.50: 거리 to 0.60 = 0.10, confidence = 0.10/0.15 = 0.67
        assert _compute_confidence(0.50) == pytest.approx(0.67)

    def test_confidence_never_exceeds_one(self):
        for score in [0.0, 0.1, 0.5, 0.9, 1.0]:
            assert _compute_confidence(score) <= 1.0

    def test_confidence_never_below_zero(self):
        for score in [0.0, 0.3, 0.6, 0.85, 1.0]:
            assert _compute_confidence(score) >= 0.0


class TestModelRegistryPredictAll:
    def test_marks_configured_primary_as_selected(self):
        registry = _make_registry()
        with patch.object(settings, "MODEL_PRIMARY", "model_b"):
            results = registry.predict_all("테스트")
        selected = [r for r in results if r["is_selected"]]
        assert len(selected) == 1
        assert selected[0]["model_name"] == "model_b"

    def test_non_primary_models_are_shadow(self):
        registry = _make_registry()
        with patch.object(settings, "MODEL_PRIMARY", "model_a"):
            results = registry.predict_all("테스트")
        shadow = [r for r in results if r["is_shadow"]]
        assert len(shadow) == 2
        assert all(r["model_name"] != "model_a" for r in shadow)

    def test_fallback_to_is_primary_when_name_not_found(self):
        registry = _make_registry()
        with patch.object(settings, "MODEL_PRIMARY", "nonexistent_model"):
            results = registry.predict_all("테스트")
        selected = [r for r in results if r["is_selected"]]
        assert selected[0]["model_name"] == "model_a"  # is_primary=True

    def test_metadata_included_in_results(self):
        registry = _make_registry()
        with patch.object(settings, "MODEL_PRIMARY", "model_a"):
            results = registry.predict_all("테스트")
        for r in results:
            assert "model_name" in r
            assert "model_version" in r
            assert "model_type" in r


class TestGetFinalResult:
    def test_primary_only_uses_selected_model(self):
        registry = _make_registry()
        predictions = _make_predictions()  # model_a is selected, score=0.20
        with patch.object(settings, "DECISION_POLICY", "primary_only"):
            result = registry.get_final_result(predictions)
        assert result["risk_score"] == 0.20
        assert result["risk_level"] == "LOW"

    def test_conservative_picks_highest_score(self):
        registry = _make_registry()
        predictions = _make_predictions()  # scores: 0.20, 0.70, 0.50 → max=0.70
        with patch.object(settings, "DECISION_POLICY", "conservative"):
            result = registry.get_final_result(predictions)
        assert result["risk_score"] == 0.70
        assert result["risk_level"] == "HIGH"

    def test_ensemble_mean_averages_scores(self):
        registry = _make_registry()
        predictions = _make_predictions()  # mean(0.20, 0.70, 0.50) = 0.47
        with patch.object(settings, "DECISION_POLICY", "ensemble_mean"):
            result = registry.get_final_result(predictions)
        assert result["risk_score"] == pytest.approx(0.47, abs=0.01)
        assert result["risk_level"] == "MEDIUM"

    def test_majority_vote_picks_most_common_level(self):
        registry = _make_registry()
        # HIGH appears twice, MEDIUM once → HIGH wins
        predictions = [
            {"model_name": "m1", "risk_score": 0.65, "risk_level": "HIGH",
             "recommended_action": "REVIEW", "is_selected": True, "is_shadow": False},
            {"model_name": "m2", "risk_score": 0.72, "risk_level": "HIGH",
             "recommended_action": "REVIEW", "is_selected": False, "is_shadow": True},
            {"model_name": "m3", "risk_score": 0.45, "risk_level": "MEDIUM",
             "recommended_action": "MONITOR", "is_selected": False, "is_shadow": True},
        ]
        with patch.object(settings, "DECISION_POLICY", "majority_vote"):
            result = registry.get_final_result(predictions)
        assert result["risk_level"] == "HIGH"

    def test_majority_vote_tie_prefers_higher_risk_level(self):
        registry = _make_registry()
        # 1 MEDIUM, 1 HIGH → tie → higher wins (HIGH)
        predictions = [
            {"model_name": "m1", "risk_score": 0.45, "risk_level": "MEDIUM",
             "recommended_action": "MONITOR", "is_selected": True, "is_shadow": False},
            {"model_name": "m2", "risk_score": 0.70, "risk_level": "HIGH",
             "recommended_action": "REVIEW", "is_selected": False, "is_shadow": True},
        ]
        with patch.object(settings, "DECISION_POLICY", "majority_vote"):
            result = registry.get_final_result(predictions)
        assert result["risk_level"] == "HIGH"

    def test_result_always_has_required_keys(self):
        registry = _make_registry()
        predictions = _make_predictions()
        for policy in ("primary_only", "conservative", "ensemble_mean", "majority_vote"):
            with patch.object(settings, "DECISION_POLICY", policy):
                result = registry.get_final_result(predictions)
            assert {"risk_score", "risk_level", "recommended_action"} <= result.keys()
