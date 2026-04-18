from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from typing import Protocol, cast

from .models import DeepScanConfig, DeepScanResult
from .text_utils import (
    canonicalize_comparison_text,
    count_alphanumeric_characters,
    count_words,
    normalize_text,
    normalized_levenshtein_similarity,
)


class DeepScanPdfSession(Protocol):
    def scan_page(self, *, page_number: int, embedded_text: str) -> DeepScanResult: ...

    def close(self) -> None: ...


class DeepScanRuntime(Protocol):
    def open_pdf(self, pdf_path: Path) -> DeepScanPdfSession: ...


class OcrEngine(Protocol):
    def recognize(self, image_path: Path) -> OcrRecognition: ...


class PdfPageRenderer(Protocol):
    def render_page_to_png(self, *, page_number: int, dpi: int) -> Path: ...

    def close(self) -> None: ...


class OcrRecognition:
    def __init__(self, *, text: str, scores: list[float]) -> None:
        self.text = text
        self.scores = scores


class PaddleOcrDeepScanRuntime:
    def __init__(
        self,
        config: DeepScanConfig,
        *,
        ocr_engine: OcrEngine | None = None,
        renderer_factory: RendererFactory | None = None,
    ) -> None:
        self._config = config
        self._ocr_engine = ocr_engine or PaddleOcrEngine(lang=config.lang)
        self._renderer_factory = renderer_factory or PyMuPdfRenderer

    def open_pdf(self, pdf_path: Path) -> DeepScanPdfSession:
        return PaddleOcrPdfSession(
            config=self._config,
            ocr_engine=self._ocr_engine,
            renderer=self._renderer_factory(pdf_path),
        )


class PaddleOcrPdfSession:
    def __init__(
        self,
        *,
        config: DeepScanConfig,
        ocr_engine: OcrEngine,
        renderer: PdfPageRenderer,
    ) -> None:
        self._config = config
        self._ocr_engine = ocr_engine
        self._renderer = renderer

    def scan_page(self, *, page_number: int, embedded_text: str) -> DeepScanResult:
        try:
            image_path = self._renderer.render_page_to_png(
                page_number=page_number,
                dpi=self._config.dpi,
            )
            recognition = self._ocr_engine.recognize(image_path)
        except Exception as exc:
            return DeepScanResult(
                backend=self._config.backend,
                lang=self._config.lang,
                rendered_dpi=self._config.dpi,
                passed=False,
                status="error",
                ocr_text_characters=0,
                ocr_text_words=0,
                error=f"Deep scan failed: {exc}",
            )

        return compare_embedded_text_to_ocr(
            embedded_text=embedded_text,
            recognition=recognition,
            config=self._config,
        )

    def close(self) -> None:
        self._renderer.close()


class PaddleOcrEngine:
    def __init__(self, *, lang: str) -> None:
        try:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Deep scan requires PaddleOCR and PaddlePaddle. "
                "Install them following the official PaddleOCR instructions."
            ) from exc

        self._lang = lang
        self._client = PaddleOCR(
            lang=lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, image_path: Path) -> OcrRecognition:
        if hasattr(self._client, "predict"):
            try:
                raw_result = self._client.predict(
                    str(image_path),
                    text_rec_score_thresh=0.0,
                )
            except TypeError:
                raw_result = self._client.predict(str(image_path))
        elif hasattr(self._client, "ocr"):
            raw_result = self._client.ocr(str(image_path), cls=False)
        else:
            raise RuntimeError("PaddleOCR client does not expose a supported inference method.")

        payload = coerce_paddle_payload(raw_result)
        texts = [str(item) for item in payload_sequence(payload, "rec_texts")]
        scores = [coerce_float(item) for item in payload_sequence(payload, "rec_scores")]
        combined_text = normalize_text(" ".join(texts))
        return OcrRecognition(text=combined_text, scores=scores)


class PyMuPdfRenderer:
    def __init__(self, pdf_path: Path) -> None:
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError(
                "Deep scan requires PyMuPDF for page rendering. Install dependencies with uv sync."
            ) from exc

        self._pymupdf = pymupdf
        self._document = pymupdf.open(pdf_path)
        self._temporary_directory = TemporaryDirectory(prefix="pdf-ocr-audit-")

    def render_page_to_png(self, *, page_number: int, dpi: int) -> Path:
        output_path = Path(self._temporary_directory.name) / f"page-{page_number:04d}.png"
        page = self._document.load_page(page_number - 1)
        pixmap = page.get_pixmap(dpi=dpi)
        pixmap.save(output_path)
        return output_path

    def close(self) -> None:
        self._document.close()
        self._temporary_directory.cleanup()


RendererFactory = Callable[[Path], PdfPageRenderer]


def build_deep_scan_runtime(config: DeepScanConfig) -> DeepScanRuntime:
    if config.backend != "paddleocr":
        raise ValueError(f"Unsupported deep scan backend: {config.backend}")
    return PaddleOcrDeepScanRuntime(config)


def compare_embedded_text_to_ocr(
    *,
    embedded_text: str,
    recognition: OcrRecognition,
    config: DeepScanConfig,
) -> DeepScanResult:
    normalized_embedded_text = canonicalize_comparison_text(embedded_text)
    normalized_ocr_text = canonicalize_comparison_text(recognition.text)
    ocr_text_characters = count_alphanumeric_characters(normalized_ocr_text)
    ocr_text_words = count_words(normalized_ocr_text)
    confidence_mean = mean(recognition.scores) if recognition.scores else None
    confidence_min = min(recognition.scores) if recognition.scores else None
    similarity = normalized_levenshtein_similarity(normalized_embedded_text, normalized_ocr_text)
    confidence_passes = confidence_mean is None or confidence_mean >= config.min_confidence

    if ocr_text_characters == 0:
        status = "no_reocr_text_detected"
        passed = False
    elif not normalized_embedded_text:
        status = "missing_text_layer_but_reocr_detected"
        passed = False
    elif similarity >= config.min_similarity and confidence_passes:
        status = "match"
        passed = True
    elif similarity >= config.min_similarity:
        status = "low_confidence"
        passed = False
    else:
        status = "mismatch"
        passed = False

    return DeepScanResult(
        backend=config.backend,
        lang=config.lang,
        rendered_dpi=config.dpi,
        passed=passed,
        status=status,
        ocr_text_characters=ocr_text_characters,
        ocr_text_words=ocr_text_words,
        text_similarity=similarity,
        ocr_confidence_mean=confidence_mean,
        ocr_confidence_min=confidence_min,
        snippet=normalized_ocr_text[:80],
    )


def coerce_paddle_payload(raw_result: object) -> dict[str, object]:
    legacy_payload = coerce_legacy_paddle_payload(raw_result)
    if legacy_payload is not None:
        return legacy_payload

    candidate = raw_result
    if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes, bytearray)):
        if not candidate:
            return {"rec_texts": [], "rec_scores": []}
        candidate = candidate[0]

    if hasattr(candidate, "json"):
        json_payload = candidate.json  # pyright: ignore[reportAttributeAccessIssue]
        candidate = json_payload() if callable(json_payload) else json_payload

    if hasattr(candidate, "to_dict"):
        to_dict = candidate.to_dict  # pyright: ignore[reportAttributeAccessIssue]
        if callable(to_dict):
            candidate = to_dict()

    if isinstance(candidate, dict):
        return cast(dict[str, object], candidate)

    raise RuntimeError(f"Unexpected PaddleOCR response structure: {type(candidate)!r}")


def payload_sequence(payload: dict[str, object], key: str) -> list[object]:
    raw_value = payload.get(key, [])
    if isinstance(raw_value, Iterable) and not isinstance(raw_value, (str, bytes, bytearray, dict)):
        return list(raw_value)
    return []


def coerce_float(value: object) -> float:
    return float(cast(float | int | str, value))


def coerce_legacy_paddle_payload(candidate: object) -> dict[str, object] | None:
    if not isinstance(candidate, Iterable) or isinstance(candidate, (str, bytes, bytearray)):
        return None

    texts: list[str] = []
    scores: list[float] = []
    for entry in candidate:
        if not isinstance(entry, Sequence) or len(entry) < 2:
            continue
        text_and_score = entry[1]
        if not isinstance(text_and_score, Sequence) or len(text_and_score) < 2:
            continue
        texts.append(str(text_and_score[0]))
        scores.append(float(text_and_score[1]))

    if not texts:
        return None
    return {"rec_texts": texts, "rec_scores": scores}
