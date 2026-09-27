"""
Mock dataset generator for SecureDerm AI.

Creates synthetic wound-like images for development and testing.
Real clinical images are not included in the repository.

Usage:
    python -m scripts.generate_mock_data
    python -m scripts.generate_mock_data --hospitals 3 --images-per-class 50
"""

import argparse
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from config.settings import DATASETS_DIR, IMAGE_SIZE
from hospital_node.dataset_loader import LABEL_MAP

# Color palettes loosely inspired by wound appearance
CLASS_COLORS = {
    "normal_healing": [(200, 170, 150), (210, 180, 160), (190, 160, 140)],
    "mild_infection": [(220, 160, 130), (230, 140, 120), (210, 150, 110)],
    "moderate_infection": [(200, 100, 80), (180, 90, 70), (190, 110, 90)],
    "severe_infection": [(160, 60, 50), (140, 50, 40), (150, 70, 60)],
}


def generate_synthetic_image(
    class_name: str,
    size: int = IMAGE_SIZE,
) -> Image.Image:
    """
    Generate a synthetic image that vaguely resembles a wound photograph.

    This is NOT medically accurate — it's purely for pipeline testing.
    """
    # Pick a random base color for this class
    base_color = random.choice(CLASS_COLORS[class_name])

    # Create background with slight variation
    img = Image.new("RGB", (size, size))
    pixels = np.zeros((size, size, 3), dtype=np.uint8)

    for c in range(3):
        channel = np.random.normal(base_color[c], 15, (size, size))
        pixels[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

    img = Image.fromarray(pixels)

    # Draw an elliptical "wound" region in the center
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    rx = random.randint(size // 6, size // 3)
    ry = random.randint(size // 6, size // 3)

    wound_color = tuple(max(0, c - random.randint(20, 60)) for c in base_color)
    draw.ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry],
        fill=wound_color,
    )

    # Add some texture / noise
    img = img.filter(ImageFilter.GaussianBlur(radius=2))

    return img


def generate_hospital_dataset(
    hospital_name: str,
    images_per_class: int = 25,
    output_dir: Path = DATASETS_DIR,
) -> Path:
    """
    Generate a mock dataset for one hospital.

    Creates:
        datasets/<hospital_name>/
            normal_healing/img_001.jpg ...
            mild_infection/img_001.jpg ...
            moderate_infection/img_001.jpg ...
            severe_infection/img_001.jpg ...
    """
    hospital_dir = output_dir / hospital_name
    total = 0

    for class_name in LABEL_MAP.keys():
        class_dir = hospital_dir / class_name
        class_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, images_per_class + 1):
            img = generate_synthetic_image(class_name)
            filename = class_dir / f"img_{i:04d}.jpg"
            img.save(filename, "JPEG", quality=90)
            total += 1

    print(f"Generated {total} images for {hospital_name} → {hospital_dir}")
    return hospital_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate mock wound datasets for SecureDerm AI"
    )
    parser.add_argument(
        "--hospitals",
        type=int,
        default=2,
        help="Number of hospital datasets to generate (default: 2)",
    )
    parser.add_argument(
        "--images-per-class",
        type=int,
        default=25,
        help="Images per class per hospital (default: 25)",
    )
    args = parser.parse_args()

    hospital_names = [f"hospital_{chr(65 + i)}" for i in range(args.hospitals)]

    for name in hospital_names:
        generate_hospital_dataset(name, images_per_class=args.images_per_class)

    print(f"\nDone. {args.hospitals} hospital datasets created in {DATASETS_DIR}")


if __name__ == "__main__":
    main()
