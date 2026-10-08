"""Tests for evaluation helpers and the predictor's ranked/calibrated outputs."""

import pytest
import torch
from PIL import Image

from config.settings import CLASS_LABELS, NUM_CLASSES
from model import inference
from model.architecture import build_model
from model.evaluation import (
    confusion_matrix,
    expected_calibration_error,
    fit_temperature,
    per_class_report,
)


class TestEvaluationHelpers:
    def test_confusion_matrix_and_report(self):
        labels = torch.tensor([0, 0, 1, 1, 2])
        preds = torch.tensor([0, 1, 1, 1, 0])
        m = confusion_matrix(labels, preds, 3)
        assert m.tolist() == [[1, 1, 0], [0, 2, 0], [1, 0, 0]]

        report = per_class_report(m)
        assert report[1]["recall"] == 1.0
        assert report[1]["precision"] == pytest.approx(0.6667, abs=1e-3)
        assert report[2]["f1"] == 0.0  # never predicted, never right
        assert [r["support"] for r in report] == [2, 2, 1]

    def test_ece_zero_for_perfectly_confident_correct(self):
        probs = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
        assert expected_calibration_error(probs, torch.tensor([0, 1])) == 0.0

    def test_ece_detects_overconfidence(self):
        probs = torch.tensor([[0.99, 0.01]] * 4)
        labels = torch.tensor([0, 1, 1, 1])  # only 25% right at 99% confidence
        assert expected_calibration_error(probs, labels) > 0.5

    def test_fit_temperature_softens_overconfident_logits(self):
        logits = torch.tensor([[10.0, 0.0]] * 10)
        labels = torch.tensor([0] * 6 + [1] * 4)  # only 60% right
        assert fit_temperature(logits, labels) > 1.0


class _Predictor(inference.WoundPredictor):
    """Skip checkpoint loading; use a randomly initialised model."""

    def __init__(self):
        self.device = "cpu"
        self.model = build_model(pretrained=False).eval()


class TestPredictorReload:
    def test_checkpoint_change_triggers_reload(self, tmp_path, monkeypatch):
        import os

        monkeypatch.setattr(inference, "CHECKPOINTS_DIR", tmp_path)
        monkeypatch.setattr(inference, "_predictor", None)
        monkeypatch.setattr(inference, "_predictor_stamp", None)
        path = tmp_path / "global_model.pt"
        torch.save(build_model(pretrained=False).state_dict(), path)

        first = inference.get_predictor()
        assert inference.get_predictor() is first  # unchanged file -> cached

        torch.save(build_model(pretrained=False).state_dict(), path)
        os.utime(path, ns=(1, 1))  # guarantee a distinct stamp on coarse clocks
        assert inference.get_predictor() is not first


class TestPredictorOutputs:
    def _image(self):
        return Image.new("RGB", (64, 64), color=(150, 80, 70))

    def test_result_has_ranked_top_predictions(self):
        result = _Predictor().predict(self._image())
        probs = [p["probability"] for p in result.top_predictions]
        assert probs == sorted(probs, reverse=True)
        assert result.top_predictions[0]["label"] == result.predicted_class
        assert 0.0 <= result.uncertainty <= 1.0
        assert sum(result.class_probabilities.values()) == pytest.approx(1.0, abs=1e-2)

    def test_batch_matches_single(self):
        predictor = _Predictor()
        imgs = [self._image(), Image.new("RGB", (64, 64), color=(10, 200, 30))]
        batch = predictor.predict_batch(imgs)
        assert len(batch) == 2
        assert batch[0].predicted_class == predictor.predict(imgs[0]).predicted_class
        assert predictor.predict_batch([]) == []

    def test_temperature_changes_confidence_not_ranking(self, monkeypatch):
        predictor = _Predictor()
        base = predictor.predict(self._image())
        monkeypatch.setattr(inference, "INFERENCE_TEMPERATURE", 5.0)
        soft = predictor.predict(self._image())
        assert soft.predicted_class == base.predicted_class
        assert soft.confidence < base.confidence
        assert soft.uncertainty > base.uncertainty

    def test_tta_returns_valid_distribution(self, monkeypatch):
        monkeypatch.setattr(inference, "INFERENCE_TTA", True)
        result = _Predictor().predict(self._image())
        assert result.predicted_class in CLASS_LABELS.values()
        assert len(result.class_probabilities) == NUM_CLASSES
