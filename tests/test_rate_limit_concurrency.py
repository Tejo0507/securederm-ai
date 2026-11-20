"""The rate-limit table is shared by the auth limiter (event-loop thread) and
the per-account limiter (worker threads). Sweeping it while another thread adds
a key used to raise "dictionary changed size during iteration".
"""

import threading
import time
from collections import deque

import pytest

from web_backend import auth as auth_module

pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def _clean_table():
    auth_module._auth_attempts.clear()
    yield
    auth_module._auth_attempts.clear()


def test_sweeping_while_other_threads_add_keys_does_not_crash():
    errors: list[BaseException] = []
    stop = threading.Event()
    stale = time.time() - 10_000

    def add_keys():
        i = 0
        while not stop.is_set():
            i += 1
            try:
                auth_module.enforce_account_rate_limit(i, "predict", 1_000_000)
            except BaseException as exc:  # noqa: BLE001 - the test reports any failure
                errors.append(exc)
                return

    def sweep():
        for _ in range(25):
            # Re-seed expired entries so every pass has real work to do.
            for n in range(300):
                auth_module._auth_attempts[f"old:{n}"] = deque([stale])
            try:
                auth_module._sweep_expired_rate_limit_entries(time.time())
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                return

    adders = [threading.Thread(target=add_keys) for _ in range(3)]
    sweeper = threading.Thread(target=sweep)
    for t in adders:
        t.start()
    sweeper.start()
    sweeper.join(timeout=60)
    stop.set()
    for t in adders:
        t.join(timeout=10)

    assert not errors, errors


def test_a_sweep_keeps_entries_that_are_still_inside_the_window():
    now = time.time()
    auth_module._auth_attempts["login:1.2.3.4"] = deque([now])
    auth_module._auth_attempts["login:old"] = deque([now - 10_000])

    auth_module._sweep_expired_rate_limit_entries(now)

    assert "login:1.2.3.4" in auth_module._auth_attempts
    assert "login:old" not in auth_module._auth_attempts
