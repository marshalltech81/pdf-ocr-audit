from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf_ocr_audit import audit as audit_module
from pdf_ocr_audit.cli import positive_integer
from pdf_ocr_audit.deep_scan import coerce_legacy_paddle_payload, coerce_paddle_payload
from pdf_ocr_audit.models import AuditReport, AuditSummary, PageAuditResult, PdfAuditResult
from pdf_ocr_audit.reporting import render_report


class ExplodingPage:
    def extract_text(self) -> str | None:
        raise RuntimeError("boom")


class EncryptedReader:
    is_encrypted = True

    def decrypt(self, _password: str) -> int:
        return 0

    @property
    def pages(self) -> list[SimpleNamespace]:
        return []


class MissingAesSupportReader:
    is_encrypted = True

    def decrypt(self, _password: str) -> int:
        raise RuntimeError("cryptography>=3.1 is required for AES algorithm")

    @property
    def pages(self) -> list[SimpleNamespace]:
        return []


def test_audit_path_rejects_missing_target(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="Target does not exist"):
        audit_module.audit_path(missing)


def test_audit_path_rejects_non_pdf_file(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Target file is not a PDF"):
        audit_module.audit_path(text_path)


def test_audit_page_reports_extraction_failure() -> None:
    result = audit_module.audit_page(ExplodingPage(), page_number=2, min_chars=10)

    assert result.has_ocr_text is False
    assert result.error == "Text extraction failed: boom"


def test_audit_pdf_reports_reader_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_reader(_path: Path) -> None:
        raise OSError("cannot read")

    pdf_path = tmp_path / "bad.pdf"
    monkeypatch.setattr(audit_module, "PdfReader", fake_reader)

    result = audit_module.audit_pdf(pdf_path, root=tmp_path, min_chars=10)

    assert result.has_error is True
    assert result.error == "Unable to read PDF: cannot read"


def test_audit_pdf_reports_missing_aes_support(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_reader(_path: Path) -> None:
        raise RuntimeError("cryptography>=3.1 is required for AES algorithm")

    pdf_path = tmp_path / "secret.pdf"
    monkeypatch.setattr(audit_module, "PdfReader", fake_reader)

    result = audit_module.audit_pdf(pdf_path, root=tmp_path, min_chars=10)

    assert result.has_error is True
    assert (
        result.error == "Encrypted PDF requires AES support from the cryptography package before "
        "password status can be checked. Run uv sync and try again."
    )


def test_audit_pdf_reports_missing_aes_support_during_decrypt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pdf_path = tmp_path / "secret.pdf"
    monkeypatch.setattr(audit_module, "PdfReader", lambda _path: MissingAesSupportReader())

    result = audit_module.audit_pdf(pdf_path, root=tmp_path, min_chars=10)

    assert result.has_error is True
    assert (
        result.error == "Encrypted PDF requires AES support from the cryptography package before "
        "password status can be checked. Run uv sync and try again."
    )


def test_audit_pdf_reports_encrypted_pdf(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "secret.pdf"
    monkeypatch.setattr(audit_module, "PdfReader", lambda _path: EncryptedReader())

    result = audit_module.audit_pdf(pdf_path, root=tmp_path, min_chars=10)

    assert result.has_error is True
    assert result.error == "Encrypted PDF: password required"


def test_display_path_falls_back_when_root_is_unrelated(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    unrelated_root = Path("/tmp/somewhere-else")

    assert audit_module._display_path(pdf_path, unrelated_root) == str(pdf_path)


def test_positive_integer_rejects_zero() -> None:
    with pytest.raises(Exception, match="greater than or equal to 1"):
        positive_integer("0")


def test_render_report_supports_text_and_json() -> None:
    page_ok = PageAuditResult(
        page_number=1,
        has_ocr_text=True,
        extracted_characters=25,
        extracted_words=4,
        snippet="This page has OCR text.",
    )
    page_bad = PageAuditResult(
        page_number=2,
        has_ocr_text=False,
        extracted_characters=0,
        extracted_words=0,
        error="extract failed",
    )
    page_dict = page_bad.to_dict()
    pdf_bad = PdfAuditResult(path="bad.pdf", page_count=2, pages=[page_ok, page_bad])
    pdf_error = PdfAuditResult(path="broken.pdf", page_count=0, error="Unable to read PDF")
    summary = AuditSummary(
        pdfs_scanned=2,
        pages_scanned=2,
        pages_passing=1,
        pages_failing=1,
        files_passing=0,
        files_failing=2,
        errors=1,
    )
    report = AuditReport(
        target="/tmp/pdfs",
        min_chars=10,
        recursive=True,
        pdfs=[pdf_bad, pdf_error],
        summary=summary,
    )

    text_output = render_report(report, output_format="text", show_all_pages=True)
    json_output = render_report(report, output_format="json", show_all_pages=False)

    assert "Failing PDFs" in text_output
    assert "page 1: ok" in text_output
    assert "error: Unable to read PDF" in text_output
    assert '"exit_code": 2' in json_output
    assert page_dict["error"] == "extract failed"
    assert report.to_dict()["summary"]["errors"] == 1


def test_render_report_supports_all_passing_text_output() -> None:
    page_ok = PageAuditResult(
        page_number=1,
        has_ocr_text=True,
        extracted_characters=18,
        extracted_words=3,
        snippet="All good.",
    )
    pdf_ok = PdfAuditResult(path="good.pdf", page_count=1, pages=[page_ok])
    summary = AuditSummary(
        pdfs_scanned=1,
        pages_scanned=1,
        pages_passing=1,
        pages_failing=0,
        files_passing=1,
        files_failing=0,
        errors=0,
    )
    report = AuditReport(
        target="/tmp/pdfs",
        min_chars=10,
        recursive=False,
        pdfs=[pdf_ok],
        summary=summary,
    )

    text_output = render_report(report, output_format="text", show_all_pages=True)

    assert "All PDFs" in text_output
    assert report.exit_code() == 0


def test_render_report_rejects_unknown_format() -> None:
    summary = AuditSummary(
        pdfs_scanned=0,
        pages_scanned=0,
        pages_passing=0,
        pages_failing=0,
        files_passing=0,
        files_failing=0,
        errors=0,
    )
    report = AuditReport(
        target="/tmp/pdfs",
        min_chars=10,
        recursive=False,
        pdfs=[],
        summary=summary,
    )

    with pytest.raises(ValueError, match="Unsupported output format"):
        render_report(report, output_format="yaml", show_all_pages=False)


def test_module_entrypoint_is_importable() -> None:
    module = importlib.import_module("pdf_ocr_audit.__main__")

    assert hasattr(module, "main")


def test_coerce_legacy_paddle_payload_reads_old_api_shape() -> None:
    payload = coerce_legacy_paddle_payload(
        [
            [None, ("alpha", 0.91)],
            [None, ("beta", 0.83)],
        ]
    )

    assert payload == {"rec_texts": ["alpha", "beta"], "rec_scores": [0.91, 0.83]}


def test_coerce_paddle_payload_handles_dict_results() -> None:
    payload = coerce_paddle_payload({"rec_texts": ["alpha"], "rec_scores": [0.91]})

    assert payload["rec_texts"] == ["alpha"]
