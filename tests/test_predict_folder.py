"""Tests for scripts/predict_folder.py."""

import csv

import pytest
from PIL import Image

from scripts import predict_folder
from tests.support import FakePredictor, FakeResult


def _image(path, color=(120, 60, 50)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color).save(path)


def _rows(output):
    with open(output, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestFindImages:
    def test_only_images_in_a_stable_order(self, tmp_path):
        for name in ["b.png", "a.JPG", "c.webp"]:
            _image(tmp_path / name)
        (tmp_path / "notes.txt").write_text("not an image")
        (tmp_path / "sub").mkdir()
        assert [p.name for p in predict_folder.find_images(tmp_path)] == [
            "a.JPG", "b.png", "c.webp"]

    def test_recursive_descends_into_subfolders(self, tmp_path):
        _image(tmp_path / "top.png")
        _image(tmp_path / "ward" / "deep.png")
        flat = predict_folder.find_images(tmp_path)
        deep = predict_folder.find_images(tmp_path, recursive=True)
        assert len(flat) == 1 and len(deep) == 2


class TestClassifyFolder:
    def test_writes_a_row_per_image_with_relative_paths(self, tmp_path):
        images = tmp_path / "in"
        _image(images / "one.png")
        _image(images / "ward" / "two.png")
        output = tmp_path / "out.csv"
        predictor = FakePredictor(FakeResult("Burns", 0.9), FakeResult("Cut", 0.3, unknown=True))

        summary = predict_folder.classify_folder(images, output, predictor, recursive=True)

        assert summary == {"images": 2, "classified": 2, "unknown": 1, "errors": 0}
        rows = _rows(output)
        assert [r["file"] for r in rows] == ["one.png", "ward/two.png"]
        assert rows[0]["predicted_class"] == "Burns" and rows[0]["is_unknown"] == "False"
        assert rows[1]["predicted_class"] == "Cut" and rows[1]["is_unknown"] == "True"
        assert rows[0]["model_id"] == "abc123def456" and rows[0]["error"] == ""

    def test_an_unreadable_image_is_reported_and_the_rest_continue(self, tmp_path):
        images = tmp_path / "in"
        _image(images / "good.png")
        (images / "broken.png").write_bytes(b"this is not a png")
        output = tmp_path / "out.csv"

        summary = predict_folder.classify_folder(images, output, FakePredictor())

        assert summary == {"images": 2, "classified": 1, "unknown": 0, "errors": 1}
        by_file = {r["file"]: r for r in _rows(output)}
        assert by_file["broken.png"]["error"] and by_file["broken.png"]["predicted_class"] == ""
        assert by_file["good.png"]["error"] == ""

    def test_batches_are_respected(self, tmp_path):
        images = tmp_path / "in"
        for n in range(5):
            _image(images / f"{n}.png")
        sizes = []

        class _Recorder(FakePredictor):
            def predict_batch(self, batch):
                sizes.append(len(batch))
                return super().predict_batch(batch)

        predict_folder.classify_folder(images, tmp_path / "o.csv", _Recorder(), batch_size=2)
        assert sizes == [2, 2, 1]

    def test_formula_like_filenames_are_neutralised(self, tmp_path):
        images = tmp_path / "in"
        _image(images / "=HYPERLINK(1).png")
        predict_folder.classify_folder(images, tmp_path / "o.csv", FakePredictor())
        assert _rows(tmp_path / "o.csv")[0]["file"].startswith("'=")

    def test_empty_folder_writes_only_a_header(self, tmp_path):
        images = tmp_path / "in"
        images.mkdir()
        output = tmp_path / "o.csv"
        summary = predict_folder.classify_folder(images, output, FakePredictor())
        assert summary["images"] == 0
        assert output.read_text(encoding="utf-8").strip() == ",".join(predict_folder.COLUMNS)


class TestCommandLine:
    def test_missing_folder_is_an_error(self, tmp_path, capsys):
        assert predict_folder.main([str(tmp_path / "nope")]) == 2
        assert "Not a folder" in capsys.readouterr().err

    def test_bad_batch_size_is_an_error(self, tmp_path, capsys):
        assert predict_folder.main([str(tmp_path), "--batch-size", "0"]) == 2

    def test_no_model_checkpoint_is_reported(self, tmp_path, monkeypatch, capsys):
        def _missing(*args, **kwargs):
            raise FileNotFoundError("No saved model found at nowhere")

        monkeypatch.setattr("model.inference.WoundPredictor", _missing)
        assert predict_folder.main([str(tmp_path)]) == 1
        assert "No saved model" in capsys.readouterr().err

    def test_end_to_end_with_a_stub_predictor(self, tmp_path, monkeypatch, capsys):
        _image(tmp_path / "in" / "a.png")
        monkeypatch.setattr("model.inference.WoundPredictor", lambda: FakePredictor())
        output = tmp_path / "results.csv"

        code = predict_folder.main([str(tmp_path / "in"), "-o", str(output)])

        assert code == 0
        assert len(_rows(output)) == 1
        assert "1 images: 1 classified (0 flagged unknown), 0 unreadable" in capsys.readouterr().out


class TestCommandLineFailures:
    def _stub(self, monkeypatch, predictor=None):
        monkeypatch.setattr("model.inference.WoundPredictor", lambda: predictor or FakePredictor())

    def test_missing_output_folders_are_created(self, tmp_path, monkeypatch, capsys):
        _image(tmp_path / "in" / "a.png")
        self._stub(monkeypatch)
        output = tmp_path / "reports" / "2026" / "out.csv"

        assert predict_folder.main([str(tmp_path / "in"), "-o", str(output)]) == 0
        assert len(_rows(output)) == 1

    def test_an_output_path_that_is_a_directory_is_reported_not_a_traceback(
        self, tmp_path, monkeypatch, capsys
    ):
        _image(tmp_path / "in" / "a.png")
        self._stub(monkeypatch)
        target = tmp_path / "already-a-folder"
        target.mkdir()

        assert predict_folder.main([str(tmp_path / "in"), "-o", str(target)]) == 2
        assert "Cannot write" in capsys.readouterr().err

    def test_a_predictor_failure_is_reported_and_the_run_exits_nonzero(
        self, tmp_path, monkeypatch, capsys
    ):
        _image(tmp_path / "in" / "a.png")

        class _Broken(FakePredictor):
            def predict_batch(self, batch):
                raise RuntimeError("out of memory")

        self._stub(monkeypatch, _Broken())
        assert predict_folder.main([str(tmp_path / "in"), "-o", str(tmp_path / "o.csv")]) == 1
        assert "out of memory" in capsys.readouterr().err

    def test_a_failed_run_does_not_leave_a_half_written_csv_behind(self, tmp_path, monkeypatch):
        images = tmp_path / "in"
        for n in range(3):
            _image(images / f"{n}.png")

        class _FailsOnSecondBatch(FakePredictor):
            calls = 0

            def predict_batch(self, batch):
                type(self).calls += 1
                if type(self).calls == 2:
                    raise RuntimeError("boom")
                return super().predict_batch(batch)

        self._stub(monkeypatch, _FailsOnSecondBatch())
        output = tmp_path / "o.csv"
        code = predict_folder.main([str(images), "-o", str(output), "--batch-size", "2"])
        assert code == 1
        assert not output.exists()

    def test_an_existing_csv_survives_a_failed_run(self, tmp_path, monkeypatch):
        _image(tmp_path / "in" / "a.png")
        output = tmp_path / "o.csv"
        output.write_text("previous,results\n", encoding="utf-8")

        class _Broken(FakePredictor):
            def predict_batch(self, batch):
                raise RuntimeError("boom")

        self._stub(monkeypatch, _Broken())
        assert predict_folder.main([str(tmp_path / "in"), "-o", str(output)]) == 1
        assert output.read_text(encoding="utf-8") == "previous,results\n"


@pytest.mark.skipif(
    not (pytest.importorskip("config.settings").CHECKPOINTS_DIR / "global_model.pt").exists(),
    reason="needs a trained checkpoint",
)
def test_works_with_the_real_model(tmp_path):
    from model.inference import WoundPredictor

    _image(tmp_path / "in" / "a.png")
    summary = predict_folder.classify_folder(
        tmp_path / "in", tmp_path / "o.csv", WoundPredictor())
    assert summary["classified"] == 1 and summary["errors"] == 0
