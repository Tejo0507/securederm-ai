"""A node waits for the round to close before training again."""

import pytest
import requests
import torch

from hospital_node import client as client_module

pytestmark = pytest.mark.federated


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _node(version=3):
    node = client_module.HospitalClient("node_x", dataset=[0])
    node.token = "t"
    node.model_version = version
    return node


def _upload(node, monkeypatch, aggregated, version):
    reply = _Resp({"aggregated": aggregated, "model_version": version})
    monkeypatch.setattr(client_module.requests, "post", lambda *a, **k: reply)
    assert node.upload_update({"w": torch.zeros(1)}, num_samples=1, loss=0.5)


def _status_replies(monkeypatch, *replies):
    """Serve `replies` in order to the status poll; record how often it asked."""
    queue, asked = list(replies), []

    def get(url, **kwargs):
        asked.append(url)
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(reply, Exception):
            raise reply
        return _Resp(reply)

    monkeypatch.setattr(client_module.requests, "get", get)
    return asked


def test_waits_until_the_aggregator_publishes_the_next_model(monkeypatch):
    node = _node(version=3)
    _upload(node, monkeypatch, aggregated=False, version=3)
    asked = _status_replies(
        monkeypatch,
        {"model_version": 3},
        requests.ConnectionError("blip"),
        {"model_version": 4},
    )

    assert node.wait_for_round_close(timeout=5, interval=0) is True
    assert len(asked) == 3
    assert node.awaiting_version is None


def test_does_not_wait_when_this_update_closed_the_round(monkeypatch):
    node = _node(version=3)
    _upload(node, monkeypatch, aggregated=True, version=4)
    asked = _status_replies(monkeypatch, {"model_version": 4})

    assert node.wait_for_round_close(timeout=5, interval=0) is True
    assert asked == []


def test_gives_up_after_the_timeout(monkeypatch):
    node = _node(version=3)
    _upload(node, monkeypatch, aggregated=False, version=3)
    _status_replies(monkeypatch, {"model_version": 3})

    assert node.wait_for_round_close(timeout=0, interval=0) is False


def test_stops_waiting_when_the_aggregator_forgot_the_node(monkeypatch):
    node = _node(version=3)
    _upload(node, monkeypatch, aggregated=False, version=3)
    asked = _status_replies(monkeypatch, {"status": "running"})   # anonymous reply

    assert node.wait_for_round_close(timeout=60, interval=0) is False
    assert len(asked) == 1
