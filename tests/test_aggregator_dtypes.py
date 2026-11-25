"""Uploaded weights must have the global model's exact tensor types."""

from collections import OrderedDict

import pytest
import torch

from aggregator.server import _check_weights_compatible

pytestmark = pytest.mark.federated


def _state(float_dtype=torch.float32, int_dtype=torch.int64) -> OrderedDict:
    return OrderedDict(
        weight=torch.ones(2, 2, dtype=float_dtype),
        steps=torch.tensor(3, dtype=int_dtype),
    )


def test_matching_types_are_accepted():
    assert _check_weights_compatible(_state(), _state()) is None


@pytest.mark.parametrize("update", [
    _state(float_dtype=torch.float16),
    _state(float_dtype=torch.float64),
    _state(int_dtype=torch.int32),
    _state(float_dtype=torch.int64),
], ids=["half", "double", "int32-counter", "integer-weights"])
def test_a_different_precision_is_refused(update):
    problem = _check_weights_compatible(update, _state())

    assert problem is not None and "wrong dtype" in problem
