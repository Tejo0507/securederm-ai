"""
Wound image dataset loader.

Supports two dataset formats:
  1. Original synthetic dataset (subfolder-based with fixed LABEL_MAP)
  2. Kaggle wound classification dataset (auto-discovered class folders)

Also provides utilities for train/val splitting and federated partitioning.
"""

from pathlib import Path
from typing import Optional

import torch
from PIL import Image
from torch.utils.data import Dataset, Subset
from torchvision import transforms

from config.settings import IMAGE_SIZE, SPLIT_SEED

# Default label mapping — subfolder name → class index
LABEL_MAP = {
    "normal_healing": 0,
    "mild_infection": 1,
    "moderate_infection": 2,
    "severe_infection": 3,
}


def get_default_transforms(training: bool = True) -> transforms.Compose:
    """Standard image transforms matching model input specs."""
    if training:
        return transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])
    else:
        return transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])


class WoundDataset(Dataset):
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
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}

        for label_name, label_idx in LABEL_MAP.items():
            class_dir = self.root_dir / label_name
            if not class_dir.is_dir():
                continue

            for img_path in sorted(class_dir.iterdir()):
                if img_path.suffix.lower() in valid_extensions:
                    self.samples.append((img_path, label_idx))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]

        # Load as RGB — medical images sometimes come as grayscale or RGBA
        image = Image.open(img_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label

    def class_distribution(self) -> dict[str, int]:
        """Return a count of samples per class (useful for debugging)."""
        counts = {name: 0 for name in LABEL_MAP}
        reverse_map = {v: k for k, v in LABEL_MAP.items()}
        for _, label in self.samples:
            counts[reverse_map[label]] += 1
        return counts


# ── Kaggle Wound Classification Dataset ─────────────────────────────────

class KaggleWoundDataset(Dataset):
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

    def _discover_classes(self) -> None:
        """Find all subdirectories and build label mapping."""
        dirs = sorted([
            d.name for d in self.root_dir.iterdir() if d.is_dir()
        ])
        self.class_names = dirs
        self.class_to_idx = {name: idx for idx, name in enumerate(dirs)}

    def _load_samples(self) -> None:
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        for class_name, label_idx in self.class_to_idx.items():
            class_dir = self.root_dir / class_name
            for img_path in sorted(class_dir.rglob("*")):
                if img_path.suffix.lower() in valid_extensions:
                    self.samples.append((img_path, label_idx))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        img_path, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label


# ── Split Utilities ──────────────────────────────────────────────────────

def split_train_val(dataset: Dataset, train_ratio: float = 0.8, seed: int = SPLIT_SEED):
    """Deterministic train/validation split. Returns (train_subset, val_subset)."""
    import torch
    n = len(dataset)
    indices = torch.randperm(n, generator=torch.Generator().manual_seed(seed)).tolist()
    split = int(n * train_ratio)
    return Subset(dataset, indices[:split]), Subset(dataset, indices[split:])


def partition_for_hospitals(
    dataset: Dataset,
    num_hospitals: int = 2,
    seed: int = SPLIT_SEED,
) -> list[Subset]:
    """Split a dataset into roughly equal partitions for federated simulation."""
    import torch
    n = len(dataset)
    indices = torch.randperm(n, generator=torch.Generator().manual_seed(seed + 1)).tolist()
    chunk = n // num_hospitals
    partitions = []
    for i in range(num_hospitals):
        start = i * chunk
        end = start + chunk if i < num_hospitals - 1 else n
        partitions.append(Subset(dataset, indices[start:end]))
    return partitions
