"""The node client treats a malformed aggregator reply as a failed step.

A 200 whose body is not the expected JSON (a proxy's HTML page, a truncated
body, an older aggregator) used to raise out of register/upload_update, which
run_round does not catch, so one bad reply took the whole node process down
instead of being retried.
"""

import pytest
import torch
from torch.utils.data import Dataset

from hospital_node import client as client_module

pytestmark = pytest.mark.federated


class _Tiny(Dataset):
    def __len__(self):
        return 4

    def __getitem__(self, i):
        return torch.zeros(1), 0


class _Resp:
    status_code = 200

    def __init__(self, body=None, bad_json=False):
        self._body = body
        self._bad_json = bad_json

    def raise_for_status(self):
        return None

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._body


@pytest.fixture
def node():
    c = client_module.HospitalClient("node_x", dataset=_Tiny())
    c.token = "t"
    return c


def _reply(monkeypatch, verb, resp):
    monkeypatch.setattr(client_module.requests, verb, lambda *a, **k: resp)


class TestRegister:
    def test_non_json_reply_fails_registration(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp(bad_json=True))
        assert node.register() is False

    def test_reply_without_a_token_fails_registration(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp({"model_version": 1}))
        assert node.register() is False

    def test_a_good_reply_still_registers(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp({"node_token": "abc", "model_version": 3}))
        assert node.register() is True
        assert node.token == "abc"


class TestUpload:
    def test_non_json_reply_is_a_failed_upload(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp(bad_json=True))
        assert node.upload_update({"w": torch.zeros(1)}, num_samples=4, loss=0.5) is False

    def test_reply_missing_fields_is_a_failed_upload(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp({"status": "accepted"}))
        assert node.upload_update({"w": torch.zeros(1)}, num_samples=4, loss=0.5) is False

    def test_a_good_reply_is_a_successful_upload(self, monkeypatch, node):
        _reply(monkeypatch, "post", _Resp({"aggregated": False, "model_version": 2}))
        assert node.upload_update({"w": torch.zeros(1)}, num_samples=4, loss=0.5) is True


class TestRoundSurvivesBadReplies:
    def test_a_malformed_upload_reply_fails_the_round_without_raising(self, monkeypatch, node):
        monkeypatch.setattr(node, "download_model", lambda: {"w": torch.zeros(1)})
        monkeypatch.setattr(
            client_module,
            "train_local",
            lambda **kw: {"weights": {"w": torch.zeros(1)}, "num_samples": 4, "loss": 0.1},
        )
        _reply(monkeypatch, "post", _Resp(bad_json=True))
        assert node.run_round(1) is False


class TestDownload:
    def test_reply_without_a_model_version_is_unusable(self, monkeypatch, node):
        import base64
        import hashlib
        import io

        buf = io.BytesIO()
        torch.save({"w": torch.zeros(1)}, buf)
        raw = buf.getvalue()
        body = {
            "weights_b64": base64.b64encode(raw).decode(),
            "weights_sha256": hashlib.sha256(raw).hexdigest(),
        }
        _reply(monkeypatch, "get", _Resp(body))
        assert node.download_model() is None
