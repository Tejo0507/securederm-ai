"""
Classify every image in a folder and write the results to a CSV file.

Usage:
    python -m scripts.predict_folder FOLDER [-o results.csv] [--recursive] [--batch-size 8]

Uses the same predictor as the web backend, so images the model does not
recognise are flagged `is_unknown` (refer for manual review) rather than being
given a confident-looking label. Unreadable files get a row with an `error`
instead of stopping the run. Only the file's path relative to FOLDER and the
result are written, never any image data.
"""

import argparse
import csv
import sys
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
COLUMNS = [
    "file", "predicted_class", "confidence", "uncertainty", "is_unknown", "model_id", "error",
]


def find_images(folder: Path, recursive: bool = False) -> list[Path]:
    """Image files directly in `folder` (or below it), in a stable order."""
    pattern = "**/*" if recursive else "*"
    return sorted(
        p for p in folder.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def _cell(value) -> str:
    """Stop spreadsheets executing a filename that starts with = + - or @."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def classify_folder(
    folder: Path, output: Path, predictor, recursive: bool = False, batch_size: int = 8,
) -> dict:
    """Classify the folder's images and write `output`; returns a count summary."""
    paths = find_images(folder, recursive)
    summary = {"images": len(paths), "classified": 0, "unknown": 0, "errors": 0}

    with open(output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)

        for start in range(0, len(paths), batch_size):
            loaded: list[tuple[Path, Image.Image]] = []
            for path in paths[start:start + batch_size]:
                name = path.relative_to(folder).as_posix()
                try:
                    with Image.open(path) as image:
                        image.load()
                        loaded.append((path, image.copy()))
                except Exception as exc:
                    summary["errors"] += 1
                    writer.writerow([_cell(name), "", "", "", "", "", _cell(type(exc).__name__)])

            if not loaded:
                continue
            results = predictor.predict_batch([image for _, image in loaded])
            for (path, _), result in zip(loaded, results):
                summary["classified"] += 1
                summary["unknown"] += bool(result.is_unknown)
                writer.writerow([
                    _cell(path.relative_to(folder).as_posix()), result.predicted_class,
                    result.confidence, result.uncertainty, result.is_unknown,
                    getattr(result, "model_id", ""), "",
                ])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a folder of wound images to CSV.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("predictions.csv"))
    parser.add_argument("-r", "--recursive", action="store_true", help="include subfolders")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)

    if not args.folder.is_dir():
        print(f"Not a folder: {args.folder}", file=sys.stderr)
        return 2
    if args.batch_size < 1:
        print("--batch-size must be at least 1", file=sys.stderr)
        return 2

    from model.inference import WoundPredictor

    try:
        predictor = WoundPredictor()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    summary = classify_folder(
        args.folder, args.output, predictor, args.recursive, args.batch_size
    )
    print(
        f"{summary['images']} images: {summary['classified']} classified "
        f"({summary['unknown']} flagged unknown), {summary['errors']} unreadable "
        f"-> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
