"""
Evaluate the final global model on the validation set.

Prints overall and per-class metrics, the confusion matrix, expected
calibration error and a suggested INFERENCE_TEMPERATURE, and saves them to
logs/evaluation.json.

Usage:
    python -m scripts.evaluate_global_model
"""

import json

import torch
from torch.utils.data import DataLoader

from config.settings import (
    BATCH_SIZE,
    CHECKPOINTS_DIR,
    CLASS_LABELS,
    KAGGLE_DATASET_DIR,
    LOGS_DIR,
    NUM_CLASSES,
)
from hospital_node.dataset_loader import KaggleWoundDataset, split_train_val
from model.architecture import build_model_for_state_dict, get_device
from model.evaluation import (
    confusion_matrix,
    expected_calibration_error,
    fit_temperature,
    per_class_report,
)


def main():
    device = get_device()
    model_path = CHECKPOINTS_DIR / "global_model.pt"

    if not model_path.exists():
        print(f"No saved model found at {model_path}")
        return

    # Load validation split
    full_ds = KaggleWoundDataset(str(KAGGLE_DATASET_DIR), training=False)
    _, val_ds = split_train_val(full_ds)
    loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    weights = torch.load(model_path, map_location=device, weights_only=True)
    model = build_model_for_state_dict(weights, device=device)

    logits_chunks, label_chunks = [], []
    with torch.no_grad():
        for images, labels in loader:
            logits_chunks.append(model(images.to(device)).cpu())
            label_chunks.append(torch.as_tensor(labels))

    logits = torch.cat(logits_chunks)
    labels = torch.cat(label_chunks)
    preds = logits.argmax(dim=1)
    probs = torch.softmax(logits, dim=1)

    matrix = confusion_matrix(labels, preds, NUM_CLASSES)
    report = per_class_report(matrix)
    for row in report:
        row["name"] = CLASS_LABELS[row["class"]]

    accuracy = (preds == labels).float().mean().item()
    supports = torch.tensor([r["support"] for r in report], dtype=torch.float)
    total = supports.sum().clamp_min(1)
    weighted = {
        key: sum(r[key] * r["support"] for r in report) / total.item()
        for key in ("precision", "recall", "f1")
    }
    ece = expected_calibration_error(probs, labels)
    temperature = fit_temperature(logits, labels)

    summary = {
        "accuracy": round(accuracy, 4),
        "weighted": {k: round(v, 4) for k, v in weighted.items()},
        "expected_calibration_error": ece,
        "suggested_temperature": temperature,
        "samples": len(labels),
        "per_class": report,
        "confusion_matrix": matrix.tolist(),
    }
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    (LOGS_DIR / "evaluation.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 52)
    print("  Final Model Evaluation")
    print("=" * 52)
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {weighted['precision']:.4f}  (weighted)")
    print(f"  Recall:    {weighted['recall']:.4f}  (weighted)")
    print(f"  F1 Score:  {weighted['f1']:.4f}  (weighted)")
    print(f"  Samples:   {len(labels)}")
    print(f"  Calibration error (ECE): {ece:.4f}")
    print(f"  Suggested INFERENCE_TEMPERATURE: {temperature}")
    print("-" * 52)
    print(f"  {'Class':<18}{'Prec':>7}{'Recall':>8}{'F1':>7}{'N':>6}")
    for r in report:
        if r["support"]:
            print(f"  {r['name']:<18}{r['precision']:>7.3f}{r['recall']:>8.3f}"
                  f"{r['f1']:>7.3f}{r['support']:>6}")
    print("=" * 52)
    print(f"  Details saved to {LOGS_DIR / 'evaluation.json'}\n")


if __name__ == "__main__":
    main()
