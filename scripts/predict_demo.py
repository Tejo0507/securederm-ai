"""
Wound image prediction demo.

Usage:
    python -m scripts.predict_demo [path_to_image]

If no image path is given, picks the first image of the validation set.
Uses the same predictor as the web backend, so the demo reflects the
real behaviour, including the "Unknown — refer for manual review" safety net.
"""

import sys
from pathlib import Path

from PIL import Image

from config.settings import KAGGLE_DATASET_DIR
from hospital_node.dataset_loader import KaggleWoundDataset, split_train_val
from model.inference import WoundPredictor


def predict_image(image_path: str) -> None:
    try:
        predictor = WoundPredictor()
    except FileNotFoundError as exc:
        print(exc)
        return

    with Image.open(image_path) as image:
        result = predictor.predict(image)

    print(f"\nImage: {image_path}")
    label = "Unknown (refer for manual review)" if result.is_unknown else result.predicted_class
    print(f"Prediction: {label}")
    print(f"Confidence: {result.confidence:.2f}  (uncertainty {result.uncertainty:.2f})")
    print("Top candidates:")
    for item in result.top_predictions:
        print(f"  {item['label']:<18}{item['probability']:.2%}")
    print()


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
