# Contributing to SecureDerm AI

Thanks for helping make private, collaborative wound diagnosis better. Bug reports, tests, docs and features are all welcome.

## Getting set up

```bash
git clone https://github.com/Tejo0507/securederm-ai.git
cd securederm-ai
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

cd web && npm ci                  # only needed for dashboard work
```

The web backend and the aggregator both run with safe defaults and no configuration; see the [README quick start](README.md#quick-start) and [docs/RUNNING.md](docs/RUNNING.md).

## Before you open a pull request

CI runs the same checks, so run them locally first:

```bash
flake8 --max-line-length=100 .     # Python lint
pytest                             # full test suite (a few dozen seconds)

cd web
npx tsc --noEmit                   # type-check
npm run lint                       # ESLint
```

- **Add tests** for new behaviour. The suite runs against an isolated database, upload directory and audit log (see `tests/conftest.py`), so tests never touch real data. Use unique e-mail addresses per test file, because the test database is shared across the session.
- **Keep commits focused** and write messages in the existing style: `type(scope): summary`, for example `feat(predict): ...`, `fix(auth): ...`, `docs: ...`, `test(...)`. Explain *why* in the body.
- **Match the surrounding code**: comment density, naming and idiom.

## Privacy rules for contributions

This project exists to keep patient data private, so changes are reviewed with that in mind:

- Never store, log or return patient images, filenames or identifiers beyond what a feature strictly needs.
- Anything that records user activity should keep to structured, non-identifying fields (see `web_backend/audit.py`).
- Don't commit real patient data, credentials or `.env` files. Test fixtures must be synthetic, and fixture passwords should be generated at run time rather than written as literals.

## Reporting bugs and ideas

Use the issue templates. For security problems, **don't open a public issue**: follow [SECURITY.md](SECURITY.md).
