from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf_ocr_audit import DeepScanConfig
from pdf_ocr_audit.audit import audit_path
from pdf_ocr_audit.deep_scan import (
    OcrRecognition,
    PaddleOcrDeepScanRuntime,
    PaddleOcrEngine,
    PaddleOcrPdfSession,
    PyMuPdfRenderer,
    build_deep_scan_runtime,
    coerce_paddle_payload,
    compare_embedded_text_to_ocr,
    payload_sequence,
)
from pdf_ocr_audit.reporting import render_report
from pdf_ocr_audit.text_utils import (
    canonicalize_comparison_text,
    levenshtein_distance,
    normalized_levenshtein_similarity,
)
from tests.helpers import create_pdf


class FakeDeepScanSession:
    def __init__(self, results_by_page: dict[int, object]) -> None:
        self._results_by_page = results_by_page
        self.closed = False

    def scan_page(self, *, page_number: int, embedded_text: str) -> object:
        result = self._results_by_page[page_number]
        if callable(result):
            return result(embedded_text)
        return result

    def close(self) -> None:
        self.closed = True


class FakeDeepScanRuntime:
    def __init__(self, session: FakeDeepScanSession) -> None:
        self.session = session

    def open_pdf(self, _pdf_path: Path) -> FakeDeepScanSession:
        return self.session


def test_canonicalize_comparison_text_normalizes_case_and_punctuation() -> None:
    assert canonicalize_comparison_text("Invoice #42\nPAID!") == "invoice 42 paid"


def test_normalized_levenshtein_similarity_handles_exact_match() -> None:
    assert normalized_levenshtein_similarity("abc", "abc") == 1.0


def test_levenshtein_distance_handles_empty_values() -> None:
    assert levenshtein_distance("", "abc") == 3


def test_compare_embedded_text_to_ocr_returns_match() -> None:
    config = DeepScanConfig(min_similarity=0.7, min_confidence=0.6)
    recognition = OcrRecognition(text="Invoice 42 paid in full", scores=[0.91, 0.88])

    result = compare_embedded_text_to_ocr(
        embedded_text="Invoice 42 paid in full.",
        recognition=recognition,
        config=config,
    )

    assert result.passed is True
    assert result.status == "match"
    assert result.text_similarity is not None
    assert result.text_similarity >= 0.7


def test_compare_embedded_text_to_ocr_flags_missing_text_layer() -> None:
    config = DeepScanConfig()
    recognition = OcrRecognition(text="Readable page text", scores=[0.93])

    result = compare_embedded_text_to_ocr(
        embedded_text="",
        recognition=recognition,
        config=config,
    )

    assert result.passed is False
    assert result.status == "missing_text_layer_but_reocr_detected"


def test_compare_embedded_text_to_ocr_flags_low_confidence() -> None:
    config = DeepScanConfig(min_similarity=0.7, min_confidence=0.95)
    recognition = OcrRecognition(text="Invoice 42 paid in full", scores=[0.81, 0.82])

    result = compare_embedded_text_to_ocr(
        embedded_text="Invoice 42 paid in full",
        recognition=recognition,
        config=config,
    )

    assert result.passed is False
    assert result.status == "low_confidence"


def test_compare_embedded_text_to_ocr_flags_no_reocr_text() -> None:
    config = DeepScanConfig()
    recognition = OcrRecognition(text="", scores=[])

    result = compare_embedded_text_to_ocr(
        embedded_text="Invoice 42 paid in full",
        recognition=recognition,
        config=config,
    )

    assert result.passed is False
    assert result.status == "no_reocr_text_detected"


def test_audit_path_uses_deep_scan_results_for_page_outcome(tmp_path: Path) -> None:
    pdf_path = tmp_path / "document.pdf"
    create_pdf(pdf_path, ["Invoice 42 paid in full"])
    deep_scan = DeepScanConfig()
    deep_result = compare_embedded_text_to_ocr(
        embedded_text="Invoice 42 paid in full",
        recognition=OcrRecognition(text="totally unrelated text", scores=[0.95]),
        config=deep_scan,
    )
    runtime = FakeDeepScanRuntime(FakeDeepScanSession({1: deep_result}))

    report = audit_path(pdf_path, deep_scan=deep_scan, deep_scan_runtime=runtime)

    assert report.summary.pages_failing == 1
    assert report.exit_code() == 1
    assert report.pdfs[0].pages[0].deep_scan is not None
    assert report.pdfs[0].pages[0].deep_scan.status == "mismatch"
    assert runtime.session.closed is True


def test_render_report_includes_deep_scan_details(tmp_path: Path) -> None:
    pdf_path = tmp_path / "document.pdf"
    create_pdf(pdf_path, ["Invoice 42 paid in full"])
    deep_scan = DeepScanConfig()
    deep_result = compare_embedded_text_to_ocr(
        embedded_text="Invoice 42 paid in full",
        recognition=OcrRecognition(text="Invoice 42 paid in full", scores=[0.92, 0.9]),
        config=deep_scan,
    )
    runtime = FakeDeepScanRuntime(FakeDeepScanSession({1: deep_result}))

    report = audit_path(
        pdf_path,
        deep_scan=deep_scan,
        deep_scan_runtime=runtime,
    )
    text_output = render_report(report, output_format="text", show_all_pages=True)

    assert "Deep scan: yes" in text_output
    assert "deep_status=match" in text_output
    assert "similarity=" in text_output


def test_payload_sequence_returns_list_for_iterable_values() -> None:
    payload = {"rec_scores": (0.9, 0.8)}

    assert payload_sequence(payload, "rec_scores") == [0.9, 0.8]


def test_coerce_paddle_payload_handles_json_attribute() -> None:
    result = [SimpleNamespace(json={"rec_texts": ["alpha"], "rec_scores": [0.9]})]

    payload = coerce_paddle_payload(result)

    assert payload["rec_texts"] == ["alpha"]


def test_coerce_paddle_payload_raises_on_unknown_structure() -> None:
    try:
        coerce_paddle_payload(object())
    except RuntimeError as exc:
        assert "Unexpected PaddleOCR response structure" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_paddle_ocr_pdf_session_returns_error_result_on_failure() -> None:
    class ExplodingRenderer:
        def render_page_to_png(self, *, page_number: int, dpi: int) -> Path:
            raise RuntimeError(f"cannot render page {page_number} at {dpi}")

        def close(self) -> None:
            return None

    class DummyEngine:
        def recognize(self, image_path: Path) -> OcrRecognition:
            raise AssertionError(f"unexpected image path: {image_path}")

    session = PaddleOcrPdfSession(
        config=DeepScanConfig(),
        ocr_engine=DummyEngine(),
        renderer=ExplodingRenderer(),
    )

    result = session.scan_page(page_number=1, embedded_text="hello")

    assert result.passed is False
    assert result.status == "error"
    assert result.error is not None


def test_build_deep_scan_runtime_rejects_unknown_backend() -> None:
    try:
        build_deep_scan_runtime(DeepScanConfig(backend="other"))
    except ValueError as exc:
        assert "Unsupported deep scan backend" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_paddle_ocr_engine_reports_missing_dependency(monkeypatch) -> None:
    original_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "paddleocr":
            raise ImportError("missing paddleocr")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError, match="Deep scan requires PaddleOCR and PaddlePaddle"):
        PaddleOcrEngine(lang="en")


def test_paddle_ocr_engine_recognize_supports_predict(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def predict(self, image_path: str, text_rec_score_thresh: float = 0.0):
            return [{"rec_texts": ["Alpha", "Beta"], "rec_scores": [0.91, 0.89]}]

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=FakeClient))

    engine = PaddleOcrEngine(lang="en")
    recognition = engine.recognize(Path("/tmp/page.png"))

    assert recognition.text == "Alpha Beta"
    assert recognition.scores == [0.91, 0.89]


def test_paddle_ocr_engine_recognize_supports_legacy_ocr(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def ocr(self, image_path: str, cls: bool = False):
            return [[None, ("Alpha", 0.91)], [None, ("Beta", 0.89)]]

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PaddleOCR=FakeClient))

    engine = PaddleOcrEngine(lang="en")
    engine._client = FakeClient()  # noqa: SLF001
    recognition = engine.recognize(Path("/tmp/page.png"))

    assert recognition.text == "Alpha Beta"
    assert recognition.scores == [0.91, 0.89]


def test_pymupdf_renderer_renders_and_closes(monkeypatch, tmp_path: Path) -> None:
    saved_paths: list[Path] = []

    class FakePixmap:
        def save(self, output_path: Path) -> None:
            saved_paths.append(output_path)
            output_path.write_text("png", encoding="utf-8")

    class FakePage:
        def get_pixmap(self, dpi: int) -> FakePixmap:
            assert dpi == 200
            return FakePixmap()

    class FakeDocument:
        def load_page(self, page_index: int) -> FakePage:
            assert page_index == 0
            return FakePage()

        def close(self) -> None:
            return None

    class FakePyMuPdfModule:
        @staticmethod
        def open(pdf_path: Path) -> FakeDocument:
            assert pdf_path == tmp_path / "document.pdf"
            return FakeDocument()

    monkeypatch.setitem(sys.modules, "pymupdf", FakePyMuPdfModule())

    renderer = PyMuPdfRenderer(tmp_path / "document.pdf")
    output_path = renderer.render_page_to_png(page_number=1, dpi=200)
    renderer.close()

    assert saved_paths == [output_path]
    assert output_path.name == "page-0001.png"


def test_paddle_ocr_deep_scan_runtime_opens_pdf_with_injected_dependencies(tmp_path: Path) -> None:
    class DummyEngine:
        def recognize(self, image_path: Path) -> OcrRecognition:
            return OcrRecognition(text=image_path.name, scores=[0.9])

    class DummyRenderer:
        def __init__(self, pdf_path: Path) -> None:
            self.pdf_path = pdf_path

        def render_page_to_png(self, *, page_number: int, dpi: int) -> Path:
            assert dpi == 200
            return self.pdf_path.with_name(f"page-{page_number}.png")

        def close(self) -> None:
            return None

    runtime = PaddleOcrDeepScanRuntime(
        DeepScanConfig(),
        ocr_engine=DummyEngine(),
        renderer_factory=DummyRenderer,
    )

    session = runtime.open_pdf(tmp_path / "document.pdf")
    result = session.scan_page(page_number=1, embedded_text="page 1")
    session.close()

    assert result.backend == "paddleocr"
