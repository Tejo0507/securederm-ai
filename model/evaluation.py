"""
Evaluation helpers for the wound classifier: per-class metrics, confusion
matrix, calibration error and temperature fitting.

Pure torch (no sklearn) so they run anywhere the model does and are cheap
to unit-test. Used by scripts/evaluate_global_model.py.
"""

import torch
import torch.nn.functional as F


def confusion_matrix(labels: torch.Tensor, preds: torch.Tensor, num_classes: int) -> torch.Tensor:
    """(num_classes, num_classes) counts; rows = true class, columns = predicted."""
    flat = labels.long() * num_classes + preds.long()
    return torch.bincount(flat, minlength=num_classes * num_classes).reshape(
        num_classes, num_classes
    )


def per_class_report(matrix: torch.Tensor) -> list[dict]:
    """Precision / recall / F1 / support for each class from a confusion matrix."""
    report = []
    for c in range(matrix.shape[0]):
        tp = matrix[c, c].item()
        fp = matrix[:, c].sum().item() - tp
        fn = matrix[c, :].sum().item() - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report.append({
            "class": c,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": int(matrix[c, :].sum().item()),
        })
    return report


def expected_calibration_error(
    probs: torch.Tensor, labels: torch.Tensor, bins: int = 10
) -> float:
    """Gap between stated confidence and actual accuracy, averaged over
    confidence bins (0 = perfectly calibrated)."""
    confidence, preds = probs.max(dim=1)
    correct = (preds == labels).float()
    edges = torch.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        in_bin = (confidence > lo) & (confidence <= hi)
        if in_bin.any():
            gap = (confidence[in_bin].mean() - correct[in_bin].mean()).abs()
            ece += in_bin.float().mean().item() * gap.item()
    return round(ece, 4)


def fit_temperature(
    logits: torch.Tensor,
    labels: torch.Tensor,
    candidates: list[float] | None = None,
) -> float:
    """Temperature minimizing validation negative log-likelihood (grid search).

    Divide logits by the returned value before softmax (see
    INFERENCE_TEMPERATURE). Does not change which class wins, only how
    confident the model sounds.
    """
    candidates = candidates or [round(0.5 + 0.1 * i, 1) for i in range(0, 46)]
    best_t, best_nll = 1.0, float("inf")
    for t in candidates:
        nll = F.cross_entropy(logits / t, labels).item()
        if nll < best_nll:
            best_t, best_nll = t, nll
    return best_t
