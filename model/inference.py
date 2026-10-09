"""
Shared inference path for the wound classifier — used by both the CLI
demo (scripts/predict_demo.py) and the web backend (/api/predict).

Adds the "Unknown" safety net the plain softmax classifier is missing:
the model only has NUM_CLASSES to choose from, so on an image of a wound
type / infection pattern it never saw in training, it will still return
one of them with a number attached. We treat max-softmax confidence
below OOD_CONFIDENCE_THRESHOLD as "the model doesn't recognize this" and
report that explicitly instead of guessing, so a novel case gets routed
to a doctor rather than mislabeled with false confidence.
"""

import hashlib
import math
from dataclasses import dataclass, field

import torch
from PIL import Image
from torchvision import transforms

from config.settings import (
    CHECKPOINTS_DIR,
    CLASS_LABELS,
    IMAGE_SIZE,
    INFERENCE_TEMPERATURE,
    INFERENCE_TTA,
    OOD_CONFIDENCE_THRESHOLD,
    TOP_K_PREDICTIONS,
)
from model.architecture import build_model_for_state_dict, get_device

_TRANSFORM = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


@dataclass
class PredictionResult:
    predicted_class: str
    confidence: float
    is_unknown: bool
    message: str
    class_probabilities: dict[str, float]
    # Ranked best-first, so a clinician sees the runner-up diagnoses too
    # (especially useful when the top class is flagged unknown).
    top_predictions: list[dict] = field(default_factory=list)
    # Normalized Shannon entropy in [0, 1]; 1 = completely undecided.
    uncertainty: float = 0.0
    # Short SHA-256 of the checkpoint that produced this result, so a clinical
    # decision can later be traced to the exact model version.
    model_id: str = ""


def _checkpoint_id(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


class WoundPredictor:
    """Loads the global model once and serves predictions with OOD flagging."""

    def __init__(self, model_path=None, device: str | None = None):
        self.device = device or get_device()
        self.model_path = model_path or (CHECKPOINTS_DIR / "global_model.pt")

        if not self.model_path.exists():
            raise FileNotFoundError(f"No saved model found at {self.model_path}")

        self.model_id = _checkpoint_id(self.model_path)
        weights = torch.load(self.model_path, map_location=self.device, weights_only=True)
        self.model = build_model_for_state_dict(weights, device=self.device)

    def _probabilities(self, batch: torch.Tensor) -> torch.Tensor:
        """Softmax probabilities for a (B, 3, H, W) batch, shape (B, classes).

        Logits are divided by INFERENCE_TEMPERATURE first (temperature
        scaling: >1 softens over-confident outputs, which makes the OOD
        confidence threshold meaningful). With INFERENCE_TTA on, predictions
        for the image and its horizontal mirror are averaged.
        """
        with torch.no_grad():
            logits = self.model(batch) / INFERENCE_TEMPERATURE
            probs = torch.softmax(logits, dim=1)
            if INFERENCE_TTA:
                flipped = torch.softmax(
                    self.model(torch.flip(batch, dims=[3])) / INFERENCE_TEMPERATURE, dim=1
                )
                probs = (probs + flipped) / 2
        return probs

    def predict(self, image: Image.Image) -> PredictionResult:
        return self.predict_batch([image])[0]

    def predict_batch(self, images: list[Image.Image]) -> list[PredictionResult]:
        """Classify several images in one forward pass."""
        if not images:
            return []
        batch = torch.stack(
            [_TRANSFORM(img.convert("RGB")) for img in images]
        ).to(self.device)
        probs = self._probabilities(batch)
        return [self._to_result(row) for row in probs]

    def _to_result(self, probs: torch.Tensor) -> PredictionResult:
        confidence, pred_idx = torch.max(probs, 0)
        confidence = confidence.item()
        pred_class = CLASS_LABELS[pred_idx.item()]

        class_probabilities = {
            CLASS_LABELS[i]: round(p.item(), 4) for i, p in enumerate(probs)
        }

        k = min(TOP_K_PREDICTIONS, len(probs))
        top_p, top_i = torch.topk(probs, k)
        top_predictions = [
            {"label": CLASS_LABELS[i.item()], "probability": round(p.item(), 4)}
            for p, i in zip(top_p, top_i)
        ]
        entropy = -(probs * torch.log(probs.clamp_min(1e-12))).sum().item()
        uncertainty = round(entropy / math.log(len(probs)), 4) if len(probs) > 1 else 0.0

        is_unknown = confidence < OOD_CONFIDENCE_THRESHOLD
        if is_unknown:
            message = (
                "Unrecognized pattern — this does not clearly match any "
                "trained class. Refer for manual review rather than trusting "
                "this label."
            )
        else:
            message = f"Predicted '{pred_class}' with {confidence:.0%} confidence."

        return PredictionResult(
            predicted_class=pred_class,
            confidence=round(confidence, 4),
            is_unknown=is_unknown,
            message=message,
            class_probabilities=class_probabilities,
            top_predictions=top_predictions,
            uncertainty=uncertainty,
            model_id=getattr(self, "model_id", ""),
        )


_predictor: WoundPredictor | None = None
_predictor_stamp: tuple[int, int] | None = None   # (mtime_ns, size) of the loaded file


def _file_stamp(path) -> tuple[int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return st.st_mtime_ns, st.st_size


def get_predictor() -> WoundPredictor:
    """Process-wide predictor, reloaded when the checkpoint file changes.

    Loading once and never again meant the web app kept serving the model
    from its first request even after the aggregator wrote a better one
    (until the whole process was restarted).
    """
    global _predictor, _predictor_stamp
    path = CHECKPOINTS_DIR / "global_model.pt"
    stamp = _file_stamp(path)
    if _predictor is None or stamp != _predictor_stamp:
        _predictor = WoundPredictor()
        _predictor_stamp = stamp
    return _predictor
