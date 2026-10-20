"""Tests for the orchestration helpers in scripts/run_demo.py."""

import pytest
import requests

from scripts import run_demo


class _Response:
    status_code = 200


class TestWaitForServer:
    def test_survives_a_read_timeout_while_the_server_warms_up(self, monkeypatch):
        # A server that has bound its port but is still loading the model
        # answers slowly: requests raises ReadTimeout, which is not a
        # ConnectionError, and used to crash the whole demo.
        outcomes = iter([requests.ReadTimeout("slow"), requests.ConnectionError(), _Response()])

        def fake_get(url, timeout):
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(run_demo.requests, "get", fake_get)
        monkeypatch.setattr(run_demo.time, "sleep", lambda seconds: None)

        assert run_demo.wait_for_server("http://aggregator.test", timeout=30) is True

    def test_gives_up_after_the_timeout(self, monkeypatch):
        def never_ready(url, timeout):
            raise requests.ReadTimeout("slow")

        clock = iter(range(0, 1000))
        monkeypatch.setattr(run_demo.requests, "get", never_ready)
        monkeypatch.setattr(run_demo.time, "sleep", lambda seconds: None)
        monkeypatch.setattr(run_demo.time, "time", lambda: next(clock))

        assert run_demo.wait_for_server("http://aggregator.test", timeout=5) is False
