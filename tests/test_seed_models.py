"""Seeding the sample registry never leaves its database session open."""

import pytest

from web_backend import main


class FakeSession:
    def __init__(self, existing=0, fail_on_commit=False):
        self.existing = existing
        self.fail_on_commit = fail_on_commit
        self.added = []
        self.closed = False
        self.rolled_back = False

    def query(self, _model):
        return self

    def count(self):
        return self.existing

    def add_all(self, rows):
        self.added.extend(rows)

    def commit(self):
        if self.fail_on_commit:
            raise RuntimeError("database is locked")

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _use(monkeypatch, session):
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    return session


def test_an_empty_registry_gets_the_samples_and_the_session_is_closed(monkeypatch):
    session = _use(monkeypatch, FakeSession(existing=0))

    main._seed_models()

    assert len(session.added) == 5
    assert session.closed


def test_a_registry_that_has_models_is_left_alone(monkeypatch):
    session = _use(monkeypatch, FakeSession(existing=3))

    main._seed_models()

    assert session.added == []
    assert session.closed


def test_a_failed_commit_rolls_back_and_still_closes_the_session(monkeypatch):
    session = _use(monkeypatch, FakeSession(existing=0, fail_on_commit=True))

    with pytest.raises(RuntimeError, match="locked"):
        main._seed_models()

    assert session.rolled_back
    assert session.closed
