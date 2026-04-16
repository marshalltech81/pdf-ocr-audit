from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pdf_ocr_audit.cli import (
    build_deep_scan_config,
    configure_third_party_logging,
    main,
    zero_to_one_float,
)
from tests.helpers import create_pdf


def test_cli_writes_json_report(tmp_path: Path) -> None:
    pdf_path = tmp_path / "good.pdf"
    output_path = tmp_path / "report.json"
    create_pdf(pdf_path, ["Plenty of OCR text on this page."])

    exit_code = main([str(pdf_path), "--format", "json", "--output", str(output_path)])

    assert exit_code == 0
    assert '"pdfs_scanned": 1' in output_path.read_text(encoding="utf-8")


def test_cli_returns_failure_when_page_missing_ocr(tmp_path: Path, capsys) -> None:
    pdf_path = tmp_path / "bad.pdf"
    create_pdf(pdf_path, [""])

    exit_code = main([str(pdf_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Failing PDFs" in captured.out
    assert "missing OCR text" in captured.out


def test_cli_exits_with_code_2_for_missing_target(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["/tmp/definitely-missing-directory"])

    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "Target does not exist" in captured.err


def test_zero_to_one_float_rejects_out_of_range_values() -> None:
    with pytest.raises(Exception, match="between 0.0 and 1.0"):
        zero_to_one_float("1.1")


def test_build_deep_scan_config_returns_expected_values() -> None:
    args = type(
        "Args",
        (),
        {
            "deep_scan": True,
            "deep_scan_lang": "en",
            "deep_scan_dpi": 300,
            "deep_min_confidence": 0.8,
            "deep_min_similarity": 0.9,
        },
    )()

    config = build_deep_scan_config(args)

    assert config is not None
    assert config.backend == "paddleocr"
    assert config.dpi == 300
    assert config.min_confidence == 0.8
    assert config.min_similarity == 0.9


def test_configure_third_party_logging_suppresses_pypdf_warnings() -> None:
    logger = logging.getLogger("pypdf")
    original_level = logger.level
    logger.setLevel(logging.WARNING)

    try:
        configure_third_party_logging()
        assert logger.level == logging.ERROR
    finally:
        logger.setLevel(original_level)


def test_configure_third_party_logging_preserves_stricter_level() -> None:
    logger = logging.getLogger("pypdf")
    original_level = logger.level
    logger.setLevel(logging.CRITICAL)

    try:
        configure_third_party_logging()
        assert logger.level == logging.CRITICAL
    finally:
        logger.setLevel(original_level)
