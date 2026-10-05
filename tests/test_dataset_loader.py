"""Tests for the wound dataset loaders and split utilities."""

import pytest
import torch
from PIL import Image
from torch.utils.data import Dataset

from hospital_node.dataset_loader import (
    KaggleWoundDataset,
    WoundDataset,
    partition_for_hospitals,
    split_train_val,
)


def _png(path, color=(120, 60, 60)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color=color).save(path)


class TestKaggleWoundDataset:
    def test_hidden_folders_are_not_classes(self, tmp_path):
        _png(tmp_path / "Abrasions" / "a.png")
        _png(tmp_path / "Bruises" / "b.png")
        _png(tmp_path / ".ipynb_checkpoints" / "junk.png")
        _png(tmp_path / "__MACOSX" / "junk.png")

        ds = KaggleWoundDataset(str(tmp_path))
        # A phantom ".ipynb_checkpoints" class sorted first used to shift
        # every real label by one.
        assert ds.class_names == ["Abrasions", "Bruises"]
        assert sorted(set(ds.labels())) == [0, 1]

    def test_skips_hidden_files_and_directories_named_like_images(self, tmp_path):
        _png(tmp_path / "Abrasions" / "a.png")
        _png(tmp_path / "Abrasions" / "._a.png")
        (tmp_path / "Abrasions" / "folder.jpg").mkdir()
        assert len(KaggleWoundDataset(str(tmp_path))) == 1

    def test_accepts_tif_and_webp(self, tmp_path):
        for name in ("a.tif", "b.webp"):
            img = Image.new("RGB", (8, 8))
            (tmp_path / "Abrasions").mkdir(exist_ok=True)
            img.save(tmp_path / "Abrasions" / name)
        assert len(KaggleWoundDataset(str(tmp_path))) == 2

    def test_too_many_class_folders_rejected(self, tmp_path):
        for i in range(11):
            _png(tmp_path / f"class_{i:02d}" / "x.png")
        with pytest.raises(RuntimeError):
            KaggleWoundDataset(str(tmp_path))

    def test_corrupt_image_is_skipped_not_fatal(self, tmp_path):
        _png(tmp_path / "Abrasions" / "a_good.png")
        bad = tmp_path / "Abrasions" / "b_bad.png"
        bad.write_bytes(b"not an image")

        ds = KaggleWoundDataset(str(tmp_path), training=False)
        names = [p.name for p, _ in ds.samples]
        for idx in range(len(ds)):
            tensor, label = ds[idx]  # must not raise for the corrupt entry
            assert tensor.shape[0] == 3
        assert "b_bad.png" in names

    def test_all_corrupt_raises(self, tmp_path):
        (tmp_path / "Abrasions").mkdir()
        (tmp_path / "Abrasions" / "bad.png").write_bytes(b"nope")
        ds = KaggleWoundDataset(str(tmp_path))
        with pytest.raises(RuntimeError):
            ds[0]

    def test_class_distribution(self, tmp_path):
        _png(tmp_path / "Abrasions" / "a.png")
        _png(tmp_path / "Abrasions" / "b.png")
        _png(tmp_path / "Bruises" / "c.png")
        assert KaggleWoundDataset(str(tmp_path)).class_distribution() == {
            "Abrasions": 2,
            "Bruises": 1,
        }


class TestLegacyWoundDataset:
    def test_ignores_hidden_files_and_loads_labels(self, tmp_path):
        _png(tmp_path / "normal_healing" / "a.png")
        _png(tmp_path / "severe_infection" / "b.png")
        _png(tmp_path / "severe_infection" / ".hidden.png")
        ds = WoundDataset(str(tmp_path))
        assert sorted(ds.labels()) == [0, 3]


class _Labelled(Dataset):
    def __init__(self, labels):
        self._labels = labels

    def __len__(self):
        return len(self._labels)

    def __getitem__(self, i):
        return torch.zeros(1), self._labels[i]

    def labels(self):
        return list(self._labels)


class TestSplit:
    def test_every_class_appears_in_both_halves(self):
        labels = [0] * 50 + [1] * 50 + [2] * 3
        train, val = split_train_val(_Labelled(labels))
        assert {labels[i] for i in train.indices} == {0, 1, 2}
        assert {labels[i] for i in val.indices} == {0, 1, 2}

    def test_split_is_disjoint_complete_and_deterministic(self):
        labels = [i % 3 for i in range(31)]
        a_train, a_val = split_train_val(_Labelled(labels))
        b_train, b_val = split_train_val(_Labelled(labels))
        assert a_train.indices == b_train.indices and a_val.indices == b_val.indices
        assert sorted(a_train.indices + a_val.indices) == list(range(31))

    def test_singleton_class_stays_in_training(self):
        labels = [0] * 10 + [1]
        train, val = split_train_val(_Labelled(labels))
        assert 10 in train.indices and 10 not in val.indices

    def test_unlabelled_dataset_falls_back_to_shuffle(self):
        class Plain(Dataset):
            def __len__(self):
                return 10

            def __getitem__(self, i):
                return torch.zeros(1), 0

        train, val = split_train_val(Plain())
        assert len(train) == 8 and len(val) == 2

    @pytest.mark.parametrize("ratio", [0.0, 1.0, -0.1, 1.5])
    def test_invalid_ratio_rejected(self, ratio):
        with pytest.raises(ValueError):
            split_train_val(_Labelled([0, 1, 0, 1]), train_ratio=ratio)

    def test_too_small_dataset_rejected(self):
        with pytest.raises(ValueError):
            split_train_val(_Labelled([0]))

    def test_partition_covers_everything_once(self):
        train, _ = split_train_val(_Labelled([i % 2 for i in range(20)]))
        parts = partition_for_hospitals(train, 3)
        flat = [i for p in parts for i in p.indices]
        assert sorted(flat) == list(range(len(train)))
