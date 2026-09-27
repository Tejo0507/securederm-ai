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

from dataclasses import dataclass

import torch
from PIL import Image
from torchvision import transforms

from config.settings import (
    CHECKPOINTS_DIR,
    CLASS_LABELS,
    IMAGE_SIZE,
    OOD_CONFIDENCE_THRESHOLD,
)
from hospital_node.privacy_layer import make_model_private
from model.architecture import build_model, get_device

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


class WoundPredictor:
    """Loads the global model once and serves predictions with OOD flagging."""

    def __init__(self, model_path=None, device: str | None = None):
        self.device = device or get_device()
        self.model_path = model_path or (CHECKPOINTS_DIR / "global_model.pt")

        if not self.model_path.exists():
            raise FileNotFoundError(f"No saved model found at {self.model_path}")

        model = build_model(pretrained=False, device=self.device)
        model = make_model_private(model)
        model = model.to(self.device)
        weights = torch.load(self.model_path, map_location=self.device, weights_only=True)
        model.load_state_dict(weights, strict=False)
        model.eval()
        self.model = model

    def predict(self, image: Image.Image) -> PredictionResult:
        tensor = _TRANSFORM(image.convert("RGB")).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze(0)

        confidence, pred_idx = torch.max(probs, 0)
        confidence = confidence.item()
        pred_class = CLASS_LABELS[pred_idx.item()]

        class_probabilities = {
            CLASS_LABELS[i]: round(p.item(), 4) for i, p in enumerate(probs)
        }

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
        )


_predictor: WoundPredictor | None = None


def get_predictor() -> WoundPredictor:
    """Lazily-initialized process-wide singleton — avoids reloading the model per request."""
    global _predictor
    if _predictor is None:
        _predictor = WoundPredictor()
    return _predictor
