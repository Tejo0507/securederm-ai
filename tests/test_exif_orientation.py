"""A photo taken with the phone turned must be seen the right way up.

Cameras usually save the sensor's pixels unrotated and note the rotation in the
EXIF "Orientation" tag. Uploads strip all metadata, so the rotation has to be
applied to the pixels first, and inference and training have to honour it too.
"""

import io

import pytest
import torch
from PIL import Image
from torchvision import transforms

from hospital_node.dataset_loader import WoundDataset
from model.inference import WoundPredictor
from web_backend.image_validation import sanitize_image

ORIENTATION_TAG = 0x0112
ROTATE_90_CW = 6   # stored landscape, meant to be viewed as portrait


def _sideways(fmt: str) -> bytes:
    """A 64x32 picture, red on the left, tagged to be turned 90 degrees clockwise.

    Viewed correctly it is 32x64 with the red half on top.
    """
    image = Image.new("RGB", (64, 32), (0, 0, 255))
    image.paste((255, 0, 0), (0, 0, 32, 32))
    exif = Image.Exif()
    exif[ORIENTATION_TAG] = ROTATE_90_CW
    buf = io.BytesIO()
    image.save(buf, format=fmt, exif=exif)
    return buf.getvalue()


def _assert_upright(image: Image.Image) -> None:
    assert image.size == (32, 64)
    top, bottom = image.getpixel((16, 8)), image.getpixel((16, 56))
    assert top[0] > 200 and top[2] < 60, f"top should be red, got {top}"
    assert bottom[2] > 200 and bottom[0] < 60, f"bottom should be blue, got {bottom}"


@pytest.mark.privacy
@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_stored_upload_is_upright_and_carries_no_metadata(fmt):
    clean, _ = sanitize_image(_sideways(fmt))

    with Image.open(io.BytesIO(clean)) as stored:
        assert ORIENTATION_TAG not in stored.getexif()
        _assert_upright(stored.convert("RGB"))


def test_predictor_sees_the_photo_upright(monkeypatch):
    seen = []

    def capture(self, batch):
        seen.append(batch)
        return torch.full((len(batch), 10), 0.1)

    monkeypatch.setattr(WoundPredictor, "_probabilities", capture)
    predictor = object.__new__(WoundPredictor)   # no checkpoint needed
    predictor.device = "cpu"

    with Image.open(io.BytesIO(_sideways("JPEG"))) as photo:
        predictor.predict(photo)

    # Channel 0 is red: after rotation it fills the top half, not the left one.
    red = seen[0][0, 0]
    assert red[:100].mean() > red[-100:].mean() + 1
    assert abs(red[:, :100].mean() - red[:, -100:].mean()) < 0.2


def test_training_loader_sees_the_photo_upright(tmp_path):
    folder = tmp_path / "normal_healing"
    folder.mkdir()
    (folder / "photo.jpg").write_bytes(_sideways("JPEG"))

    dataset = WoundDataset(str(tmp_path), transform=transforms.Compose([]), training=False)
    image, _ = dataset[0]

    _assert_upright(image)
