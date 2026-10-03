"""
Federated Averaging (FedAvg) implementation.

Aggregates model weights from multiple hospital nodes using
weighted averaging based on each node's dataset size.

Reference: McMahan et al., "Communication-Efficient Learning
of Deep Networks from Decentralized Data" (2017).
"""

from collections import OrderedDict

import torch


def _validate_updates(node_updates: list[dict]) -> None:
    """Reject empty, inconsistent, or negative-weight update sets."""
    if not node_updates:
        raise ValueError("Cannot aggregate — no node updates received.")

    reference = node_updates[0]["weights"]
    for update in node_updates:
        if update["num_samples"] < 0:
            raise ValueError("num_samples must not be negative.")
        state = update["weights"]
        if set(state.keys()) != set(reference.keys()):
            raise ValueError("Node updates have mismatched state_dict keys.")
        for key, tensor in state.items():
            if tensor.shape != reference[key].shape:
                raise ValueError(f"Shape mismatch for '{key}' across node updates.")


def _combine(node_updates: list[dict], coefficients: list[float]) -> OrderedDict:
    """Weighted sum of state_dicts that preserves each tensor's dtype.

    Floating-point tensors are averaged. Integer buffers (e.g. BatchNorm's
    ``num_batches_tracked``) are averaged in float64 and rounded back, so
    they stay integer-typed instead of silently becoming floats.
    """
    reference = node_updates[0]["weights"]
    aggregated: OrderedDict = OrderedDict()

    for key, ref_tensor in reference.items():
        if ref_tensor.is_floating_point():
            acc = torch.zeros_like(ref_tensor)
            for update, coef in zip(node_updates, coefficients):
                acc += update["weights"][key] * coef
            aggregated[key] = acc
        else:
            acc = torch.zeros_like(ref_tensor, dtype=torch.float64)
            for update, coef in zip(node_updates, coefficients):
                acc += update["weights"][key].to(torch.float64) * coef
            aggregated[key] = acc.round().to(ref_tensor.dtype)

    return aggregated


def federated_average(
    node_updates: list[dict],
) -> OrderedDict:
    """
    Compute the weighted average of model weights from all nodes.

    Args:
        node_updates: List of dicts, each containing:
            - "weights": model state_dict (OrderedDict)
            - "num_samples": int, number of training samples at that node

    Returns:
        Aggregated state_dict representing the new global model.

    Raises:
        ValueError: If no updates are provided, the updates are
            inconsistent with each other, or the sample total is zero.
    """
    _validate_updates(node_updates)

    # Total samples across all nodes (for weighting)
    total_samples = sum(update["num_samples"] for update in node_updates)

    if total_samples == 0:
        raise ValueError("Total sample count is zero — cannot compute weights.")

    # Each node contributes proportional to its data size
    coefficients = [update["num_samples"] / total_samples for update in node_updates]
    return _combine(node_updates, coefficients)


def simple_average(
    node_updates: list[dict],
) -> OrderedDict:
    """
    Unweighted average — each node contributes equally.
    Useful for testing when dataset sizes are identical.
    """
    _validate_updates(node_updates)

    n = len(node_updates)
    return _combine(node_updates, [1.0 / n] * n)
