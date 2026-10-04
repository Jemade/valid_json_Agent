# Structured Output Agent

[![CI](https://github.com/Jemade/valid_json_Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Jemade/valid_json_Agent/actions/workflows/ci.yml)

A Python extraction pipeline that turns model responses into validated invoice objects. It handles recoverable JSON formatting issues, checks schema and arithmetic constraints, and requests corrections within a bounded retry budget.

## Features

- Prompt building, JSON recovery, and Pydantic validation.
- Required fields, extra-field checks, and invoice consistency rules.
- Corrective prompts with validation details.
- OpenAI, Anthropic, and deterministic mock adapters.
- Async FastAPI endpoints and a command-line interface.
- Structured logs, attempt history, and process-local metrics.

## Run locally

Requires Python 3.11 or newer.

```bash
git clone https://github.com/Jemade/valid_json_Agent.git
cd valid_json_Agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs.

Try the command-line fixture:

```bash
python -m app.cli extract tests/fixtures/invoice_valid.txt --provider mock
```

Mock mode returns a deterministic authored response. To extract with a live provider, configure its API key, select `openai` or `anthropic`, and choose a supported model. Settings are in `app/config.py`.

## Verification

```bash
pytest -q
ruff check app tests
```

[Golden failure fixtures](tests/fixtures/golden_failures/README.md) cover malformed JSON and invalid invoice outputs.

## Code map

- `app/agent/`: prompt, parser, validator, and retry logic.
- `app/providers/`: provider adapters.
- `app/schemas/`: invoice schema and consistency checks.
- `app/telemetry/`: logging and metrics.
- `tests/`: regression checks and fixtures.

## Current scope

Schema validity does not establish that extracted values match the original document. Mock mode demonstrates validation, not semantic extraction. Metrics reset with the process; the service is not a persistent document-processing queue.

## Engineering and contribution guide

Read the [engineering notes](docs/ENGINEERING.md) for implementation boundaries and verification commands, the [review checklist](docs/REVIEW_CHECKLIST.md) for evidence still required, and [CONTRIBUTING.md](CONTRIBUTING.md) to propose changes. Report vulnerabilities through [SECURITY.md](SECURITY.md).

[![Repository hygiene](https://github.com/Jemade/valid_json_Agent/actions/workflows/repository-hygiene.yml/badge.svg)](https://github.com/Jemade/valid_json_Agent/actions/workflows/repository-hygiene.yml)
