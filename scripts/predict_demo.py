"""
Wound image prediction demo.

Usage:
    python -m scripts.predict_demo [path_to_image]

If no image path is given, picks a random image from the validation set.
"""

import sys
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from config.settings import (
    CHECKPOINTS_DIR,
    IMAGE_SIZE,
    KAGGLE_DATASET_DIR,
)
from hospital_node.dataset_loader import KaggleWoundDataset, split_train_val
from model.architecture import build_model_for_state_dict, get_device


def predict_image(image_path: str) -> None:
    device = get_device()
    model_path = CHECKPOINTS_DIR / "global_model.pt"

    if not model_path.exists():
        print(f"No saved model found at {model_path}")
        return

    # Discover class names from dataset folder
    ds = KaggleWoundDataset(str(KAGGLE_DATASET_DIR), training=False)
    class_names = ds.class_names

    weights = torch.load(model_path, map_location=device, weights_only=True)
    model = build_model_for_state_dict(weights, device=device)

    # Preprocess image
    transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    image = Image.open(image_path).convert("RGB")
    tensor = transform(image).unsqueeze(0).to(device)

    # Inference
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1)
        confidence, pred_idx = torch.max(probs, 1)

    pred_class = class_names[pred_idx.item()]
    conf = confidence.item()

    print(f"\nImage: {image_path}")
    print(f"Prediction: {pred_class}")
    print(f"Confidence: {conf:.2f}\n")


def main():
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Pick a sample image from the validation set
        ds = KaggleWoundDataset(str(KAGGLE_DATASET_DIR), training=False)
        _, val_ds = split_train_val(ds)
        # Get the first validation sample's path
        idx = val_ds.indices[0]
        image_path = str(ds.samples[idx][0])
        print(f"No image specified — using validation sample: {Path(image_path).name}")

    predict_image(image_path)


if __name__ == "__main__":
    main()
