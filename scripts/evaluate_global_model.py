"""
Evaluate the final global model on the validation set.

Usage:
    python -m scripts.evaluate_global_model
"""

import torch
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from config.settings import (
    KAGGLE_DATASET_DIR,
    CHECKPOINTS_DIR,
    BATCH_SIZE,
)
from hospital_node.dataset_loader import KaggleWoundDataset, split_train_val
from model.architecture import build_model_for_state_dict, get_device


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

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            _, preds = torch.max(outputs, 1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.tolist() if isinstance(labels, torch.Tensor) else labels)

    accuracy = accuracy_score(all_labels, all_preds)
    precision = precision_score(all_labels, all_preds, average="weighted", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="weighted", zero_division=0)
    f1 = f1_score(all_labels, all_preds, average="weighted", zero_division=0)

    print("\n" + "=" * 40)
    print("  Final Model Evaluation")
    print("=" * 40)
    print(f"  Accuracy:  {accuracy:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall:    {recall:.4f}")
    print(f"  F1 Score:  {f1:.4f}")
    print(f"  Samples:   {len(all_labels)}")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    main()
