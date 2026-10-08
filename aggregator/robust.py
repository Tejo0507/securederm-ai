"""
Defences against bad or malicious model updates.

A single hospital (buggy, compromised, or poisoning on purpose) can submit
weights far from everyone else's and, under plain FedAvg, drag the global
model with it. Clipping each update's distance from the current global model
bounds how much any one node can move it in a round.
"""

import hashlib
from collections import OrderedDict


def update_norm(weights: dict, reference: dict) -> float:
    """L2 norm of (weights - reference) over all floating-point tensors."""
    total = 0.0
    for key, ref in reference.items():
        if ref.is_floating_point():
            total += (weights[key].double() - ref.double()).pow(2).sum().item()
    return total ** 0.5


def clip_update(weights: dict, reference: dict, max_norm: float) -> tuple[OrderedDict, float, bool]:
    """Scale the update so its distance from `reference` is at most `max_norm`.

    Returns (weights, original_norm, was_clipped). Integer buffers are left
    untouched. `max_norm <= 0` disables clipping.
    """
    norm = update_norm(weights, reference)
    if max_norm <= 0 or norm <= max_norm or norm == 0.0:
        return OrderedDict(weights), norm, False

    scale = max_norm / norm
    clipped: OrderedDict = OrderedDict()
    for key, tensor in weights.items():
        ref = reference[key]
        if tensor.is_floating_point():
            clipped[key] = (ref + (tensor - ref) * scale).to(tensor.dtype)
        else:
            clipped[key] = tensor
    return clipped, norm, True


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

