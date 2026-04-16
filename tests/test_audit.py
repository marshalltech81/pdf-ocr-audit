from __future__ import annotations

from pathlib import Path

from pdf_ocr_audit.audit import (
    audit_path,
    count_alphanumeric_characters,
    count_words,
    normalize_text,
)
from tests.helpers import create_pdf


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("hello\n\nworld\t  again") == "hello world again"


def test_character_and_word_counts() -> None:
    text = "Invoice 42 paid"
    assert count_alphanumeric_characters(text) == 13
    assert count_words(text) == 3


def test_audit_path_marks_blank_page_as_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "mixed.pdf"
    create_pdf(pdf_path, ["OCR text is present here.", ""])

    report = audit_path(pdf_path, min_chars=10)

    assert report.summary.pdfs_scanned == 1
    assert report.summary.pages_scanned == 2
    assert report.summary.pages_failing == 1
    assert report.exit_code() == 1
    assert report.pdfs[0].pages[0].has_ocr_text is True
    assert report.pdfs[0].pages[1].has_ocr_text is False


def test_audit_path_supports_directory_scan(tmp_path: Path) -> None:
    create_pdf(tmp_path / "good.pdf", ["This page has enough OCR text."])
    create_pdf(tmp_path / "bad.pdf", [""])

    report = audit_path(tmp_path, min_chars=10)

    assert report.summary.pdfs_scanned == 2
    assert report.summary.files_passing == 1
    assert report.summary.files_failing == 1
    assert sorted(pdf.path for pdf in report.pdfs) == ["bad.pdf", "good.pdf"]


def test_recursive_scan_finds_nested_pdfs(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    create_pdf(nested / "good.pdf", ["This page has enough OCR text."])

    report = audit_path(tmp_path, recursive=True)

    assert report.summary.pdfs_scanned == 1
    assert report.pdfs[0].path == "nested/good.pdf"


def test_empty_directory_raises_file_not_found(tmp_path: Path) -> None:
    try:
        audit_path(tmp_path)
    except FileNotFoundError as exc:
        assert "No PDF files found" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
