from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class DeepScanConfig:
    backend: str = "paddleocr"
    lang: str = "en"
    dpi: int = 200
    min_confidence: float = 0.7
    min_similarity: float = 0.75

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class DeepScanResult:
    backend: str
    lang: str
    rendered_dpi: int
    passed: bool
    status: str
    ocr_text_characters: int
    ocr_text_words: int
    text_similarity: float | None = None
    ocr_confidence_mean: float | None = None
    ocr_confidence_min: float | None = None
    snippet: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class PageAuditResult:
    page_number: int
    has_ocr_text: bool
    extracted_characters: int
    extracted_words: int
    snippet: str = ""
    deep_scan: DeepScanResult | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        if self.error is not None or not self.has_ocr_text:
            return False
        if self.deep_scan is None:
            return True
        return self.deep_scan.passed

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


@dataclass(slots=True)
class PdfAuditResult:
    path: str
    page_count: int
    pages: list[PageAuditResult] = field(default_factory=list)
    error: str | None = None

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def failing_pages(self) -> list[PageAuditResult]:
        return [page for page in self.pages if not page.passed]

    @property
    def passed(self) -> bool:
        return not self.has_error and all(page.passed for page in self.pages)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["passed"] = self.passed
        return payload


@dataclass(slots=True)
class AuditSummary:
    pdfs_scanned: int
    pages_scanned: int
    pages_passing: int
    pages_failing: int
    files_passing: int
    files_failing: int
    errors: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class AuditReport:
    target: str
    min_chars: int
    recursive: bool
    pdfs: list[PdfAuditResult]
    summary: AuditSummary
    deep_scan: DeepScanConfig | None = None

    @property
    def has_failures(self) -> bool:
        return self.summary.pages_failing > 0

    @property
    def has_errors(self) -> bool:
        return self.summary.errors > 0

    def exit_code(self) -> int:
        if self.has_errors:
            return 2
        if self.has_failures:
            return 1
        return 0

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "min_chars": self.min_chars,
            "recursive": self.recursive,
            "deep_scan": None if self.deep_scan is None else self.deep_scan.to_dict(),
            "summary": self.summary.to_dict(),
            "pdfs": [pdf.to_dict() for pdf in self.pdfs],
            "exit_code": self.exit_code(),
        }
