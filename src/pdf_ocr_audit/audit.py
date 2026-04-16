from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from .deep_scan import DeepScanRuntime, build_deep_scan_runtime
from .models import (
    AuditReport,
    AuditSummary,
    DeepScanConfig,
    PageAuditResult,
    PdfAuditResult,
)
from .text_utils import count_alphanumeric_characters, count_words, normalize_text

_MISSING_AES_SUPPORT_ERROR = "cryptography>=3.1 is required for AES algorithm"


class TextExtractablePage(Protocol):
    def extract_text(self) -> str | None: ...


@dataclass(slots=True)
class ExtractedPageText:
    normalized_text: str
    extracted_characters: int
    extracted_words: int
    snippet: str
    error: str | None = None


def audit_path(
    path: str | Path,
    *,
    recursive: bool = False,
    min_chars: int = 10,
    deep_scan: DeepScanConfig | None = None,
    deep_scan_runtime: DeepScanRuntime | None = None,
) -> AuditReport:
    target = Path(path).expanduser().resolve()
    pdf_paths = discover_pdf_paths(target, recursive=recursive)
    runtime = deep_scan_runtime
    if deep_scan is not None and runtime is None:
        runtime = build_deep_scan_runtime(deep_scan)

    pdf_results = [
        audit_pdf(
            pdf_path,
            root=target,
            min_chars=min_chars,
            deep_scan=deep_scan,
            deep_scan_runtime=runtime,
        )
        for pdf_path in pdf_paths
    ]
    summary = build_summary(pdf_results)

    return AuditReport(
        target=str(target),
        min_chars=min_chars,
        recursive=recursive,
        deep_scan=deep_scan,
        pdfs=pdf_results,
        summary=summary,
    )


def discover_pdf_paths(target: Path, *, recursive: bool) -> list[Path]:
    if not target.exists():
        raise FileNotFoundError(f"Target does not exist: {target}")

    if target.is_file():
        if target.suffix.lower() != ".pdf":
            raise ValueError(f"Target file is not a PDF: {target}")
        return [target]

    if not target.is_dir():
        raise ValueError(f"Target is neither a file nor a directory: {target}")

    iterator = target.rglob("*") if recursive else target.iterdir()
    pdf_paths = sorted(
        (path for path in iterator if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: str(path).lower(),
    )

    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found under: {target}")

    return pdf_paths


def audit_pdf(
    path: Path,
    *,
    root: Path,
    min_chars: int,
    deep_scan: DeepScanConfig | None = None,
    deep_scan_runtime: DeepScanRuntime | None = None,
) -> PdfAuditResult:
    display_path = _display_path(path, root)

    try:
        reader = PdfReader(path)
    except Exception as exc:
        return PdfAuditResult(
            path=display_path,
            page_count=0,
            error=_format_pdf_error("Unable to read PDF", exc),
        )

    if reader.is_encrypted:
        try:
            decrypt_result = reader.decrypt("")
        except Exception as exc:
            return PdfAuditResult(
                path=display_path,
                page_count=0,
                error=_format_pdf_error("Encrypted PDF", exc),
            )

        if decrypt_result == 0:
            return PdfAuditResult(
                path=display_path,
                page_count=0,
                error="Encrypted PDF: password required",
            )

    deep_scan_session = (
        deep_scan_runtime.open_pdf(path) if deep_scan is not None and deep_scan_runtime else None
    )
    pages: list[PageAuditResult] = []
    try:
        for page_number, page in enumerate(reader.pages, start=1):
            extracted_text = extract_page_text(page)
            page_result = build_page_audit_result(
                extracted_text,
                page_number=page_number,
                min_chars=min_chars,
            )
            if deep_scan_session is not None:
                page_result.deep_scan = deep_scan_session.scan_page(
                    page_number=page_number,
                    embedded_text=extracted_text.normalized_text,
                )
            pages.append(page_result)
    finally:
        if deep_scan_session is not None:
            deep_scan_session.close()

    return PdfAuditResult(path=display_path, page_count=len(pages), pages=pages)


def audit_page(page: TextExtractablePage, *, page_number: int, min_chars: int) -> PageAuditResult:
    extracted_text = extract_page_text(page)
    return build_page_audit_result(extracted_text, page_number=page_number, min_chars=min_chars)


def extract_page_text(page: TextExtractablePage) -> ExtractedPageText:
    try:
        raw_text = page.extract_text() or ""
    except Exception as exc:
        return ExtractedPageText(
            normalized_text="",
            extracted_characters=0,
            extracted_words=0,
            snippet="",
            error=f"Text extraction failed: {exc}",
        )

    normalized_text = normalize_text(raw_text)
    return ExtractedPageText(
        normalized_text=normalized_text,
        extracted_characters=count_alphanumeric_characters(normalized_text),
        extracted_words=count_words(normalized_text),
        snippet=normalized_text[:80],
    )


def build_page_audit_result(
    extracted_text: ExtractedPageText,
    *,
    page_number: int,
    min_chars: int,
) -> PageAuditResult:
    return PageAuditResult(
        page_number=page_number,
        has_ocr_text=(
            extracted_text.error is None and extracted_text.extracted_characters >= min_chars
        ),
        extracted_characters=extracted_text.extracted_characters,
        extracted_words=extracted_text.extracted_words,
        snippet=extracted_text.snippet,
        error=extracted_text.error,
    )


def build_summary(pdf_results: list[PdfAuditResult]) -> AuditSummary:
    pages_scanned = sum(pdf.page_count for pdf in pdf_results)
    pages_failing = sum(len(pdf.failing_pages) for pdf in pdf_results)
    pages_passing = pages_scanned - pages_failing
    errors = sum(1 for pdf in pdf_results if pdf.has_error)
    files_passing = sum(1 for pdf in pdf_results if pdf.passed)
    files_failing = len(pdf_results) - files_passing

    return AuditSummary(
        pdfs_scanned=len(pdf_results),
        pages_scanned=pages_scanned,
        pages_passing=pages_passing,
        pages_failing=pages_failing,
        files_passing=files_passing,
        files_failing=files_failing,
        errors=errors,
    )


def _display_path(path: Path, root: Path) -> str:
    if root.is_file():
        return path.name

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _format_pdf_error(prefix: str, exc: Exception) -> str:
    message = str(exc)
    if _MISSING_AES_SUPPORT_ERROR in message:
        return (
            "Encrypted PDF requires AES support from the cryptography package before "
            "password status can be checked. Run uv sync and try again."
        )
    return f"{prefix}: {message}"
