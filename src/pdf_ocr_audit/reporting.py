from __future__ import annotations

import json

from .models import AuditReport, PageAuditResult


def render_report(report: AuditReport, *, output_format: str, show_all_pages: bool) -> str:
    if output_format == "json":
        return json.dumps(report.to_dict(), indent=2)

    if output_format == "text":
        return render_text_report(report, show_all_pages=show_all_pages)

    raise ValueError(f"Unsupported output format: {output_format}")


def render_text_report(report: AuditReport, *, show_all_pages: bool) -> str:
    summary = report.summary
    lines = [
        "OCR audit summary",
        f"  Target: {report.target}",
        f"  Minimum characters per page: {report.min_chars}",
        f"  Recursive scan: {'yes' if report.recursive else 'no'}",
        (
            "  Deep scan: no"
            if report.deep_scan is None
            else (
                "  Deep scan: yes "
                f"({report.deep_scan.backend}, lang={report.deep_scan.lang}, "
                f"dpi={report.deep_scan.dpi}, "
                f"min_similarity={report.deep_scan.min_similarity:.2f}, "
                f"min_confidence={report.deep_scan.min_confidence:.2f})"
            )
        ),
        f"  PDFs scanned: {summary.pdfs_scanned}",
        f"  Pages scanned: {summary.pages_scanned}",
        f"  Pages passing: {summary.pages_passing}",
        f"  Pages failing: {summary.pages_failing}",
        f"  Files passing: {summary.files_passing}",
        f"  Files failing: {summary.files_failing}",
        f"  Errors: {summary.errors}",
    ]

    failing_pdfs = [pdf for pdf in report.pdfs if pdf.has_error or not pdf.passed]
    if failing_pdfs:
        lines.append("")
        lines.append("Failing PDFs")
        for pdf in failing_pdfs:
            lines.append(f"- {pdf.path}")
            if pdf.has_error:
                lines.append(f"  error: {pdf.error}")
                continue

            pages = pdf.pages if show_all_pages else [page for page in pdf.pages if not page.passed]
            for page in pages:
                status = format_page_status(page)
                details = format_page_details(page)
                lines.append(f"  page {page.page_number}: {status} ({details})")

    elif show_all_pages:
        lines.append("")
        lines.append("All PDFs")
        for pdf in report.pdfs:
            lines.append(f"- {pdf.path}")
            for page in pdf.pages:
                lines.append(f"  page {page.page_number}: ok ({format_page_details(page)})")

    return "\n".join(lines)


def format_page_status(page: PageAuditResult) -> str:
    if page.error:
        return "text extraction failed"
    if not page.has_ocr_text:
        if page.deep_scan and page.deep_scan.status == "missing_text_layer_but_reocr_detected":
            return "missing embedded OCR text"
        return "missing OCR text"
    if page.deep_scan is not None and not page.deep_scan.passed:
        return f"deep scan {page.deep_scan.status.replace('_', ' ')}"
    return "ok"


def format_page_details(page: PageAuditResult) -> str:
    detail_parts = [
        f"chars={page.extracted_characters}",
        f"words={page.extracted_words}",
    ]
    if page.error:
        detail_parts.append(f"error={page.error}")
    elif page.snippet:
        detail_parts.append(f'snippet="{page.snippet}"')

    if page.deep_scan is not None:
        detail_parts.append(f"deep_status={page.deep_scan.status}")
        detail_parts.append(f"reocr_chars={page.deep_scan.ocr_text_characters}")
        if page.deep_scan.text_similarity is not None:
            detail_parts.append(f"similarity={page.deep_scan.text_similarity:.2f}")
        if page.deep_scan.ocr_confidence_mean is not None:
            detail_parts.append(f"confidence={page.deep_scan.ocr_confidence_mean:.2f}")
        if page.deep_scan.error:
            detail_parts.append(f"deep_error={page.deep_scan.error}")
        elif page.deep_scan.snippet:
            detail_parts.append(f'deep_snippet="{page.deep_scan.snippet}"')

    return ", ".join(detail_parts)
