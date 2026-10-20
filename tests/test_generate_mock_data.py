"""Tests for the argument handling in scripts/generate_mock_data.py.

generate_hospital_dataset is stubbed throughout so no test writes images
into the real datasets/ directory.
"""

import re

import pytest

from scripts import generate_mock_data


@pytest.fixture
def created(monkeypatch):
    names: list[str] = []
    monkeypatch.setattr(
        generate_mock_data,
        "generate_hospital_dataset",
        lambda name, **kwargs: names.append(name),
    )
    return names


def _run(monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["generate_mock_data", *args])
    generate_mock_data.main()


@pytest.mark.parametrize(
    "args",
    [
        ["--hospitals", "0"],
        ["--hospitals", "-1"],
        ["--hospitals", "27"],     # past 'Z' the names become hospital_[, hospital_\ ...
        ["--images-per-class", "0"],
        ["--images-per-class", "-5"],
    ],
)
def test_rejects_counts_that_cannot_produce_a_usable_dataset(monkeypatch, created, args):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, *args)

    assert exc.value.code == 2
    assert created == []


def test_the_largest_allowed_run_names_hospitals_a_to_z(monkeypatch, created):
    _run(monkeypatch, "--hospitals", "26")

    assert created[0] == "hospital_A" and created[-1] == "hospital_Z"
    assert all(re.fullmatch(r"hospital_[A-Z]", name) for name in created)
    assert len(created) == 26
