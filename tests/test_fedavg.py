"""Tests for the FedAvg aggregation algorithm."""

from collections import OrderedDict

import pytest
import torch

from aggregator.fedavg import federated_average, simple_average


def _make_dummy_state_dict(value: float) -> OrderedDict:
    """Create a minimal state_dict with a known value for testing."""
    return OrderedDict({
        "layer.weight": torch.tensor([value, value]),
        "layer.bias": torch.tensor([value]),
    })


class TestFederatedAverage:
    def test_single_node(self):
        updates = [{"weights": _make_dummy_state_dict(1.0), "num_samples": 100}]
        result = federated_average(updates)
        assert torch.allclose(result["layer.weight"], torch.tensor([1.0, 1.0]))

    def test_equal_weight_nodes(self):
        updates = [
            {"weights": _make_dummy_state_dict(2.0), "num_samples": 50},
            {"weights": _make_dummy_state_dict(4.0), "num_samples": 50},
        ]
        result = federated_average(updates)
        # Should be exactly 3.0 (midpoint)
        assert torch.allclose(result["layer.weight"], torch.tensor([3.0, 3.0]))

    def test_weighted_averaging(self):
        # Node A has 3x more data → its weight should dominate
        updates = [
            {"weights": _make_dummy_state_dict(1.0), "num_samples": 300},
            {"weights": _make_dummy_state_dict(5.0), "num_samples": 100},
        ]
        result = federated_average(updates)
        # Expected: (1.0 * 300 + 5.0 * 100) / 400 = 800/400 = 2.0
        assert torch.allclose(result["layer.weight"], torch.tensor([2.0, 2.0]))

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            federated_average([])


class TestSimpleAverage:
    def test_two_nodes(self):
        updates = [
            {"weights": _make_dummy_state_dict(0.0), "num_samples": 10},
            {"weights": _make_dummy_state_dict(10.0), "num_samples": 10},
        ]
        result = simple_average(updates)
        assert torch.allclose(result["layer.weight"], torch.tensor([5.0, 5.0]))


class TestFedAvgRobustness:
    def test_preserves_integer_buffer_dtype(self):
        def sd(v, n):
            return OrderedDict({"w": torch.tensor([v]), "bn.num_batches_tracked": torch.tensor(n)})

        result = federated_average([
            {"weights": sd(1.0, 10), "num_samples": 1},
            {"weights": sd(3.0, 20), "num_samples": 1},
        ])
        assert result["bn.num_batches_tracked"].dtype == torch.long
        assert result["w"].dtype == torch.float32

    def test_mismatched_keys_raise(self):
        a = _make_dummy_state_dict(1.0)
        b = OrderedDict({"other": torch.tensor([1.0])})
        with pytest.raises(ValueError):
            federated_average([
                {"weights": a, "num_samples": 1},
                {"weights": b, "num_samples": 1},
            ])

    def test_mismatched_shapes_raise(self):
        a = _make_dummy_state_dict(1.0)
        b = OrderedDict({"layer.weight": torch.tensor([1.0]), "layer.bias": torch.tensor([1.0])})
        with pytest.raises(ValueError):
            simple_average([
                {"weights": a, "num_samples": 1},
                {"weights": b, "num_samples": 1},
            ])

    def test_negative_samples_raise(self):
        with pytest.raises(ValueError):
            federated_average([
                {"weights": _make_dummy_state_dict(1.0), "num_samples": -5},
                {"weights": _make_dummy_state_dict(1.0), "num_samples": 10},
            ])
