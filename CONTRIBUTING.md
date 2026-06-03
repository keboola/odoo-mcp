# Contributing

Thanks for your interest in improving the Odoo MCP Server! Contributions of all
kinds are welcome — bug reports, fixes, new tools, and documentation.

## Getting set up

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Development workflow

1. Create a feature branch from `main` (`feature/…`, `fix/…`, `docs/…`).
2. Make your change with tests.
3. Run the checks below locally.
4. Open a pull request describing **what** changed and **why**.

## Before you push

```bash
ruff check .          # lint
mypy src/             # type check
pytest tests/unit -v  # unit tests (no external services needed)
```

All three must pass. CI runs the same checks plus a dependency security scan.

## Coding guidelines

- Python 3.12, type hints on public functions, `pathlib` over `os.path`.
- **Never hardcode secrets or configuration** — load from the environment via
  `Settings` and fail fast if required values are missing. No silent defaults.
- Keep employee-scoped tools constrained to the authenticated user; the
  `employee_id` must always come from the OAuth token, never from tool input.
- Add tests for new behaviour. Keep unit tests free of network/Odoo dependencies
  (use mocks/`respx`); integration tests skip gracefully without credentials.
- New per-instance behaviour should be opt-in via a `Settings` field with a
  stock-Odoo-safe default, and documented in `.env.example` and the README.

## Adding a new tool

1. Define the `Tool` and its handler in the appropriate `tools/*.py` module.
2. Register its required scopes in `TOOL_SCOPE_REQUIREMENTS` (`config.py`).
3. If it writes data, add it to `WRITE_TOOLS` for rate limiting.
4. Add unit tests and document it in the README tool tables.

## License

By contributing you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
