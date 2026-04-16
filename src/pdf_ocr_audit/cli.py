from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from .audit import audit_path
from .models import DeepScanConfig
from .reporting import render_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf-ocr-audit",
        description="Audit PDFs to confirm each page contains extractable OCR text.",
    )
    parser.add_argument("path", help="PDF file or directory to audit.")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Walk subdirectories when the target path is a directory.",
    )
    parser.add_argument(
        "--min-chars",
        type=positive_integer,
        default=10,
        help="Minimum extracted alphanumeric characters required per page. Default: 10.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format. Default: text.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path for saving the report instead of printing to stdout.",
    )
    parser.add_argument(
        "--show-all-pages",
        action="store_true",
        help="Include passing pages in text output.",
    )
    parser.add_argument(
        "--deep-scan",
        action="store_true",
        help="Re-render each page and compare the embedded text layer against PaddleOCR output.",
    )
    parser.add_argument(
        "--deep-scan-lang",
        default="en",
        help="PaddleOCR language code for deep scan mode. Default: en.",
    )
    parser.add_argument(
        "--deep-scan-dpi",
        type=positive_integer,
        default=200,
        help="Rasterization DPI for deep scan mode. Default: 200.",
    )
    parser.add_argument(
        "--deep-min-confidence",
        type=zero_to_one_float,
        default=0.7,
        help=(
            "Minimum average PaddleOCR confidence required for a deep scan page pass. "
            "Default: 0.70."
        ),
    )
    parser.add_argument(
        "--deep-min-similarity",
        type=zero_to_one_float,
        default=0.75,
        help=(
            "Minimum text similarity required between embedded text and PaddleOCR output. "
            "Default: 0.75."
        ),
    )
    return parser


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be greater than or equal to 1")
    return parsed


def zero_to_one_float(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("value must be between 0.0 and 1.0")
    return parsed


def build_deep_scan_config(args: argparse.Namespace) -> DeepScanConfig | None:
    if not args.deep_scan:
        return None

    return DeepScanConfig(
        backend="paddleocr",
        lang=args.deep_scan_lang,
        dpi=args.deep_scan_dpi,
        min_confidence=args.deep_min_confidence,
        min_similarity=args.deep_min_similarity,
    )


def configure_third_party_logging() -> None:
    # pypdf emits warning logs for malformed-but-readable PDFs. Keep CLI output
    # focused on audit results instead of parser recovery noise, without
    # overriding a stricter user-provided setting such as CRITICAL.
    pypdf_logger = logging.getLogger("pypdf")
    if pypdf_logger.getEffectiveLevel() < logging.ERROR:
        pypdf_logger.setLevel(logging.ERROR)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    deep_scan = build_deep_scan_config(args)
    configure_third_party_logging()

    try:
        report = audit_path(
            args.path,
            recursive=args.recursive,
            min_chars=args.min_chars,
            deep_scan=deep_scan,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(status=2, message=f"{parser.prog}: {exc}\n")

    rendered = render_report(report, output_format=args.format, show_all_pages=args.show_all_pages)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
