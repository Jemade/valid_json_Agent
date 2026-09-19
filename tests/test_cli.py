import argparse
from pathlib import Path

import pytest

from app.cli import run_extract
from app.providers.mock_provider import MockProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_cli_extract_success(tmp_path, valid_invoice_json, monkeypatch):
    doc_file = tmp_path / "test_doc.txt"
    doc_file.write_text("Invoice Number: INV-100\nTotal: $100.00")

    mock = MockProvider(responses=[valid_invoice_json])
    monkeypatch.setattr("app.cli.create_provider", lambda *args, **kwargs: mock)

    args = argparse.Namespace(
        command="extract",
        filepath=str(doc_file),
        provider="mock",
        model=None,
        max_retries=3,
    )
    exit_code = await run_extract(args)
    assert exit_code == 0


@pytest.mark.asyncio
async def test_cli_extract_file_not_found():
    args = argparse.Namespace(
        command="extract",
        filepath="non_existent_file_xyz.txt",
        provider="mock",
        model=None,
        max_retries=3,
    )
    exit_code = await run_extract(args)
    assert exit_code == 1


@pytest.mark.asyncio
async def test_cli_extract_exhausted_failure(tmp_path, monkeypatch):
    doc_file = tmp_path / "test_doc.txt"
    doc_file.write_text("Invoice")

    bad_output = '{"broken": true}'
    mock = MockProvider(responses=[bad_output, bad_output, bad_output])
    monkeypatch.setattr("app.cli.create_provider", lambda *args, **kwargs: mock)

    args = argparse.Namespace(
        command="extract",
        filepath=str(doc_file),
        provider="mock",
        model=None,
        max_retries=3,
    )
    exit_code = await run_extract(args)
    assert exit_code == 1
