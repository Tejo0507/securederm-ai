"""End-to-end federated round: real local training on two simulated hospitals
(differential privacy on), real aggregation on the server, then the new
global model is loaded exactly as the predictor would load it.

Run just these from VS Code's Testing panel (marker: federated) or with
    pytest -m federated
"""

import base64
import hashlib
import io

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset

import aggregator.server as server_module
from aggregator.robust import update_norm
from hospital_node import train as train_module
from model.architecture import build_model_for_state_dict

pytestmark = [pytest.mark.federated, pytest.mark.privacy, pytest.mark.slow]


class _Hospital(Dataset):
    """Tiny synthetic 'wounds': class is encoded in the image brightness."""

    def __init__(self, n=12, seed=0):
        gen = torch.Generator().manual_seed(seed)
        self.labels = [i % 3 for i in range(n)]
        self.images = [
            torch.randn(3, 32, 32, generator=gen) * 0.1 + label for label in self.labels
        ]

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.images[idx], self.labels[idx]


@pytest.fixture
def client():
    with TestClient(server_module.app) as c:
        yield c


def _upload(client, name, token, result, base_version):
    buf = io.BytesIO()
    torch.save(result["weights"], buf)
    raw = buf.getvalue()
    return client.post("/training/update", json={
        "hospital_id": name,
        "model_weights_b64": base64.b64encode(raw).decode(),
        "num_samples": result["num_samples"],
        "training_loss": result["loss"],
        "base_version": base_version,
        "weights_sha256": hashlib.sha256(raw).hexdigest(),
    }, headers={"X-Node-Token": token})


def test_two_hospitals_complete_a_private_round(client, tmp_path, monkeypatch):
    from hospital_node import privacy_layer

    monkeypatch.setattr(train_module, "USE_DIFFERENTIAL_PRIVACY", True)
    monkeypatch.setattr(privacy_layer, "LOGS_DIR", tmp_path)  # keep ledgers out of logs/
    server_module.pending_updates.clear()

    nodes = {}
    for name in ("e2e_a", "e2e_b"):
        nodes[name] = client.post(
            "/node/register", json={"hospital_id": name, "dataset_size": 12}
        ).json()["node_token"]

    version_before = server_module.model_version
    global_before = {k: v.clone() for k, v in server_module.global_weights.items()}

    responses = []
    for seed, (name, token) in enumerate(nodes.items()):
        download = client.get("/model/latest", headers={"X-Node-Token": token}).json()
        weights = torch.load(
            io.BytesIO(base64.b64decode(download["weights_b64"])),
            map_location="cpu", weights_only=True,
        )
        result = train_module.train_local(
            dataset=_Hospital(seed=seed), global_weights=weights,
            batch_size=4, epochs=1, node_id=name,
        )
        # Privacy was actually accounted for this round.
        assert result["epsilon"] is not None and result["epsilon"] > 0
        responses.append(_upload(client, name, token, result, download["model_version"]))

    assert [r.status_code for r in responses] == [200, 200]
    assert responses[-1].json()["aggregated"] is True
    assert server_module.model_version == version_before + 1

    # The new global model genuinely moved, and every value is finite.
    assert update_norm(server_module.global_weights, global_before) > 0
    assert all(
        torch.isfinite(v).all()
        for v in server_module.global_weights.values() if v.is_floating_point()
    )

    # Both ledgers were written, one per node.
    assert {p.name for p in tmp_path.glob("privacy_ledger_*.json")} == {
        "privacy_ledger_e2e_a.json", "privacy_ledger_e2e_b.json",
    }

    # The aggregated model loads strictly, as the predictor would load it.
    model = build_model_for_state_dict(dict(server_module.global_weights))
    with torch.no_grad():
        assert model(torch.randn(1, 3, 32, 32)).shape == (1, 10)
