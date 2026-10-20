"""Tests for the orchestration helpers in scripts/run_demo.py."""

import pytest
import requests

from scripts import run_demo


class _Response:
    status_code = 200


class _FakeProcess:
    def __init__(self, exit_code):
        self.exit_code = exit_code

    def wait(self, timeout=None):
        return self.exit_code

    def terminate(self):
        pass

    def kill(self):
        pass


class TestMain:
    @pytest.fixture
    def pipeline(self, monkeypatch):
        """Fake subprocesses; returns a setter for the two clients' exit codes
        and the list of follow-up scripts (evaluate / plot / predict) that ran."""
        state = {"codes": [0, 0]}
        follow_ups: list = []
        spawned: list = []

        def fake_popen(command, **kwargs):
            # First process is the aggregator, then hospital_A, then hospital_B.
            code = 0 if not spawned else state["codes"][len(spawned) - 1]
            spawned.append(command)
            return _FakeProcess(code)

        monkeypatch.setattr(run_demo.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(run_demo.subprocess, "run", lambda command, **kw: follow_ups.append(command))
        monkeypatch.setattr(run_demo, "wait_for_server", lambda url: True)
        monkeypatch.setattr(run_demo, "save_round_metrics", lambda url, token="": [])
        monkeypatch.setattr(run_demo, "save_global_model", lambda url, token="": True)

        def set_client_codes(a, b):
            state["codes"] = [a, b]

        return set_client_codes, follow_ups

    def test_a_clean_run_exits_zero_and_runs_the_follow_up_steps(self, pipeline, capsys):
        _, follow_ups = pipeline

        assert run_demo.main() == 0

        assert len(follow_ups) == 3
        assert "Demo Complete" in capsys.readouterr().out

    def test_a_failed_client_fails_the_demo_instead_of_reporting_success(self, pipeline, capsys):
        set_client_codes, follow_ups = pipeline
        set_client_codes(0, 1)

        assert run_demo.main() == 1

        # Evaluating and demoing a model that never finished training would
        # present stale or untrained results as the outcome of this run.
        assert follow_ups == []
        assert "Demo Complete" not in capsys.readouterr().out

    def test_an_aggregator_that_never_starts_exits_nonzero(self, pipeline, monkeypatch):
        monkeypatch.setattr(run_demo, "wait_for_server", lambda url: False)

        assert run_demo.main() == 1


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
