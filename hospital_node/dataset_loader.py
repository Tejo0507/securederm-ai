"""
Wound image dataset loader.

Supports two dataset formats:
  1. Original synthetic dataset (subfolder-based with fixed LABEL_MAP)
  2. Kaggle wound classification dataset (auto-discovered class folders)

Also provides utilities for train/val splitting and federated partitioning.
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import torch
from PIL import Image, UnidentifiedImageError
from torch.utils.data import Dataset, Subset
from torchvision import transforms

from config.settings import CLASS_LABELS, IMAGE_SIZE, NUM_CLASSES, SPLIT_SEED

logger = logging.getLogger("hospital_node.dataset")

# Default label mapping — subfolder name → class index
LABEL_MAP = {
    "normal_healing": 0,
    "mild_infection": 1,
    "moderate_infection": 2,
    "severe_infection": 3,
}

# One list for both loaders (they used to disagree on .webp, and neither
# accepted .tif).
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]


def get_default_transforms(training: bool = True) -> transforms.Compose:
    """Standard image transforms matching model input specs."""
    steps = [transforms.Resize((IMAGE_SIZE, IMAGE_SIZE))]
    if training:
        steps += [
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
        ]
    steps += [
        transforms.ToTensor(),
        transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
    ]
    return transforms.Compose(steps)


def _is_hidden(path: Path) -> bool:
    """Dotfiles/dirs and macOS/Jupyter debris (.ipynb_checkpoints, __MACOSX, ._x.jpg)."""
    return path.name.startswith((".", "_"))


class _ImageSamplesDataset(Dataset):
    """Shared behaviour for datasets backed by a list of (path, label) pairs."""

    root_dir: Path
    transform: Optional[transforms.Compose]
    samples: list[tuple[Path, int]]

    def __len__(self) -> int:
        return len(self.samples)

    def _load(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        # Load as RGB — medical images sometimes come as grayscale or RGBA
        with Image.open(img_path) as img:
            image = img.convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        # One truncated/corrupt file must not abort an entire training round
        # (it surfaces mid-epoch, after the privacy budget is already being
        # spent). Fall through to the next readable sample instead, and say
        # which file was skipped.
        n = len(self.samples)
        for offset in range(n):
            candidate = (idx + offset) % n
            try:
                return self._load(candidate)
            except (OSError, UnidentifiedImageError, ValueError, SyntaxError) as exc:
                # Log the sample index, never the filename: clinical file names
                # often embed patient names or record numbers.
                logger.warning(
                    "Skipping unreadable image #%d: %s", candidate, type(exc).__name__
                )
        raise RuntimeError(f"No readable images in {self.root_dir}.")

    def labels(self) -> list[int]:
        return [label for _, label in self.samples]


class WoundDataset(_ImageSamplesDataset):
    """
    PyTorch Dataset for wound classification images.

    Reads images from a root directory organized into subfolders
    (one per class). Each subfolder name must match a key in LABEL_MAP.
    """

    def __init__(
        self,
        root_dir: str,
        transform: Optional[transforms.Compose] = None,
        training: bool = True,
    ):
        self.root_dir = Path(root_dir)
        self.transform = transform or get_default_transforms(training)
        self.samples: list[tuple[Path, int]] = []

        if not self.root_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {self.root_dir}")

        self._load_samples()

        if len(self.samples) == 0:
            raise RuntimeError(
                f"No images found in {self.root_dir}. "
                f"Expected subfolders: {list(LABEL_MAP.keys())}"
            )

    def _load_samples(self) -> None:
        """Walk subdirectories and collect (path, label) pairs."""
        for entry in sorted(self.root_dir.iterdir()):
            if entry.is_dir() and not _is_hidden(entry) and entry.name not in LABEL_MAP:
                logger.warning(
                    "Ignoring folder '%s': not one of %s", entry.name, list(LABEL_MAP)
                )

        for label_name, label_idx in LABEL_MAP.items():
            class_dir = self.root_dir / label_name
            if not class_dir.is_dir():
                continue

            for img_path in sorted(class_dir.iterdir()):
                if (
                    img_path.is_file()
                    and not _is_hidden(img_path)
                    and img_path.suffix.lower() in IMAGE_EXTENSIONS
                ):
                    self.samples.append((img_path, label_idx))

    def class_distribution(self) -> dict[str, int]:
        """Return a count of samples per class (useful for debugging)."""
        counts = {name: 0 for name in LABEL_MAP}
        reverse_map = {v: k for k, v in LABEL_MAP.items()}
        for _, label in self.samples:
            counts[reverse_map[label]] += 1
        return counts


# ── Kaggle Wound Classification Dataset ─────────────────────────────────

class KaggleWoundDataset(_ImageSamplesDataset):
    """
    PyTorch Dataset for the Kaggle wound classification dataset.

    Auto-discovers class folders and assigns integer labels sorted
    alphabetically by folder name.
    """

    def __init__(
        self,
        root_dir: str,
        transform: Optional[transforms.Compose] = None,
        training: bool = True,
    ):
        self.root_dir = Path(root_dir)
        self.transform = transform or get_default_transforms(training)
        self.samples: list[tuple[Path, int]] = []
        self.class_names: list[str] = []
        self.class_to_idx: dict[str, int] = {}

        if not self.root_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {self.root_dir}")

        self._discover_classes()
        self._load_samples()

        if len(self.samples) == 0:
            raise RuntimeError(f"No images found in {self.root_dir}.")

        # The model's head has NUM_CLASSES outputs and predictions are named
        # via CLASS_LABELS. A dataset with more folders would make
        # CrossEntropyLoss fail mid-training with an opaque index error; one
        # whose folder order differs would silently mislabel predictions.
        if len(self.class_names) > NUM_CLASSES:
            raise RuntimeError(
                f"{self.root_dir} has {len(self.class_names)} class folders but the "
                f"model has {NUM_CLASSES} outputs."
            )
        expected = [CLASS_LABELS[i] for i in range(NUM_CLASSES)]
        if self.class_names != expected[: len(self.class_names)]:
            logger.warning(
                "Dataset class folders %s do not match the model's CLASS_LABELS %s; "
                "predictions may be reported under the wrong names.",
                self.class_names, expected,
            )

    def _discover_classes(self) -> None:
        """Find all class subdirectories and build the label mapping.

        Hidden folders (.ipynb_checkpoints, __MACOSX, ...) are not classes:
        they sort before the real ones, so counting them shifted every label
        by one and added a phantom empty class.
        """
        dirs = sorted(
            d.name for d in self.root_dir.iterdir() if d.is_dir() and not _is_hidden(d)
        )
        self.class_names = dirs
        self.class_to_idx = {name: idx for idx, name in enumerate(dirs)}

    def _load_samples(self) -> None:
        for class_name, label_idx in self.class_to_idx.items():
            class_dir = self.root_dir / class_name
            for img_path in sorted(class_dir.rglob("*")):
                if (
                    img_path.is_file()
                    and img_path.suffix.lower() in IMAGE_EXTENSIONS
                    and not any(
                        part.startswith((".", "_"))
                        for part in img_path.relative_to(class_dir).parts
                    )
                ):
                    self.samples.append((img_path, label_idx))

    def class_distribution(self) -> dict[str, int]:
        """Return a count of samples per class folder."""
        counts = {name: 0 for name in self.class_names}
        for _, label in self.samples:
            counts[self.class_names[label]] += 1
        return counts


# ── Split Utilities ──────────────────────────────────────────────────────

def split_train_val(dataset: Dataset, train_ratio: float = 0.8, seed: int = SPLIT_SEED):
    """Deterministic, class-stratified train/validation split.

    Returns (train_subset, val_subset). When the dataset exposes labels, each
    class is split separately so every class with at least two samples appears
    in both halves — a plain shuffle can leave a small class absent from
    validation, which silently inflates the metrics. Datasets without labels
    fall back to a plain shuffled split.
    """
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be strictly between 0 and 1.")
    n = len(dataset)
    if n < 2:
        raise ValueError("Need at least 2 samples to split into train and validation.")

    generator = torch.Generator().manual_seed(seed)
    labels = dataset.labels() if hasattr(dataset, "labels") else None

    if labels is None:
        indices = torch.randperm(n, generator=generator).tolist()
        split = min(max(int(n * train_ratio), 1), n - 1)
        return Subset(dataset, indices[:split]), Subset(dataset, indices[split:])

    by_class: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        by_class[label].append(idx)

    train_idx: list[int] = []
    val_idx: list[int] = []
    for label in sorted(by_class):
        members = by_class[label]
        order = torch.randperm(len(members), generator=generator).tolist()
        members = [members[i] for i in order]
        if len(members) == 1:
            train_idx.extend(members)  # can't split a singleton; keep it for training
            continue
        split = min(max(round(len(members) * train_ratio), 1), len(members) - 1)
        train_idx.extend(members[:split])
        val_idx.extend(members[split:])

    # Shuffle so the subsets aren't ordered class-by-class.
    train_idx = [train_idx[i] for i in torch.randperm(len(train_idx), generator=generator).tolist()]
    val_idx = [val_idx[i] for i in torch.randperm(len(val_idx), generator=generator).tolist()]
    return Subset(dataset, train_idx), Subset(dataset, val_idx)


def partition_for_hospitals(
    dataset: Dataset,
    num_hospitals: int = 2,
    seed: int = SPLIT_SEED,
) -> list[Subset]:
    """Split a dataset into roughly equal partitions for federated simulation."""
    n = len(dataset)
    if num_hospitals < 1 or num_hospitals > n:
        raise ValueError(
            f"Cannot split {n} samples across {num_hospitals} hospitals "
            "(every hospital needs at least one sample)."
        )
    indices = torch.randperm(n, generator=torch.Generator().manual_seed(seed + 1)).tolist()
    chunk = n // num_hospitals
    partitions = []
    for i in range(num_hospitals):
        start = i * chunk
        end = start + chunk if i < num_hospitals - 1 else n
        partitions.append(Subset(dataset, indices[start:end]))
    return partitions
