"""The audit logger is first used from several request threads at once."""

import logging
import threading
import time

from web_backend import audit as audit_module


def test_concurrent_first_use_installs_exactly_one_handler(tmp_path, monkeypatch):
    """If two threads both see "no handler yet" and both add one, every event is
    written twice and a hospital's activity list shows duplicates. Slowing the
    handler's construction makes that interleaving certain."""
    path = tmp_path / "concurrent" / "audit.log"
    monkeypatch.setattr(audit_module, "AUDIT_LOG_PATH", path)
    for handler in list(audit_module._logger.handlers):
        audit_module._logger.removeHandler(handler)
        handler.close()

    real_handler = audit_module.RotatingFileHandler

    def _slow_handler(*args, **kwargs):
        time.sleep(0.05)
        return real_handler(*args, **kwargs)

    monkeypatch.setattr(audit_module, "RotatingFileHandler", _slow_handler)

    barrier = threading.Barrier(8)

    def _first_use():
        barrier.wait()
        audit_module.audit("probe", 1, n=threading.get_ident())

    threads = [threading.Thread(target=_first_use) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    handlers = [h for h in audit_module._logger.handlers if isinstance(h, logging.Handler)]
    try:
        assert len(handlers) == 1
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 8          # one line per event, none duplicated
    finally:
        for handler in list(audit_module._logger.handlers):
            audit_module._logger.removeHandler(handler)
            handler.close()
