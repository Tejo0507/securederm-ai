"""
Federated Averaging (FedAvg) implementation.

Aggregates model weights from multiple hospital nodes using
weighted averaging based on each node's dataset size.

Reference: McMahan et al., "Communication-Efficient Learning
of Deep Networks from Decentralized Data" (2017).
"""

import copy
from collections import OrderedDict


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
        ValueError: If no updates are provided.
    """
    if not node_updates:
        raise ValueError("Cannot aggregate — no node updates received.")

    # Total samples across all nodes (for weighting)
    total_samples = sum(update["num_samples"] for update in node_updates)

    if total_samples == 0:
        raise ValueError("Total sample count is zero — cannot compute weights.")

    # Start with a zeroed copy of the first node's state_dict
    reference = node_updates[0]["weights"]
    aggregated: OrderedDict = OrderedDict()

    for key in reference.keys():
        aggregated[key] = copy.deepcopy(reference[key]).float() * 0.0

    # Weighted sum: each node contributes proportional to its data size
    for update in node_updates:
        weight = update["num_samples"] / total_samples
        state = update["weights"]

        for key in aggregated.keys():
            aggregated[key] += state[key].float() * weight

    return aggregated


def simple_average(
    node_updates: list[dict],
) -> OrderedDict:
    """
    Unweighted average — each node contributes equally.
    Useful for testing when dataset sizes are identical.
    """
    if not node_updates:
        raise ValueError("Cannot aggregate — no node updates received.")

    n = len(node_updates)
    reference = node_updates[0]["weights"]
    aggregated: OrderedDict = OrderedDict()

    for key in reference.keys():
        aggregated[key] = copy.deepcopy(reference[key]).float() * 0.0

    for update in node_updates:
        for key in aggregated.keys():
            aggregated[key] += update["weights"][key].float() / n

    return aggregated
