# Contributing to valid_json_Agent

Start with a reproducible defect or a concrete user need. Search existing issues and keep changes focused.

## Development checks

Use a Python virtual environment. From `.`, run:

```sh
pip install -e ".[dev]"
ruff check app tests
pytest -q
```

Read the README for runtime versions and service prerequisites. Additional CI jobs are defined in `.github/workflows/`; do not describe a skipped check as passed.

For a behavior fix, add a regression that fails before the fix and passes afterward. Explain expected and actual behavior, link the issue from the PR, and document tradeoffs. Use synthetic fixtures and never publish credentials or private data.

A review should check correctness, boundaries, failure handling and tests. Independent review is distinct from automated checks. Follow [SECURITY.md](SECURITY.md) for vulnerability reports and [engineering notes](docs/ENGINEERING.md) for product boundaries.
