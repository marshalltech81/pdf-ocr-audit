# pdf-ocr-audit

`pdf-ocr-audit` checks PDFs page-by-page to confirm each page has extractable text that can act as an OCR text layer.

This is useful when you have a directory full of PDFs and want to quickly answer:

- Which PDFs are fully OCR-backed?
- Which specific pages are missing extractable text?
- Can I fail a CI job or automation step when OCR coverage is incomplete?

## What Counts As "OCR Support"

The tool opens each PDF, extracts text from every page, normalizes whitespace, and counts alphanumeric characters. A page is considered OCR-backed when the extracted text meets or exceeds a configurable minimum character threshold.

By default:

- `min_chars = 10`
- a page with no extractable text fails
- a page with only a tiny fragment such as a page number may also fail

This makes the default behavior stricter than a simple "did *any* text extract?" check, which helps reduce false positives from decorative or incidental text.

## Two Scan Modes

The tool now supports two complementary audit modes:

- Standard scan: checks whether each page already contains an extractable PDF text layer.
- Deep scan: rasterizes each page, runs `PaddleOCR`, and compares the fresh OCR output back to the embedded PDF text layer.

Deep scan is useful when you want a stronger quality signal than "text exists" and need to estimate whether the embedded OCR text is plausibly accurate.

## Quick Start

### 1. Sync the environment with `uv`

```bash
uv sync --dev
```

### 2. Audit a directory of PDFs

```bash
uv run pdf-ocr-audit /path/to/pdfs --recursive
```

You can also run the module directly:

```bash
uv run python -m pdf_ocr_audit /path/to/pdfs --recursive
```

### 3. Emit machine-readable JSON

```bash
uv run pdf-ocr-audit /path/to/pdfs --recursive --format json --output report.json
```

### 4. Run the deeper PaddleOCR verification mode

```bash
uv run pdf-ocr-audit /path/to/pdfs --recursive --deep-scan
```

## Installing Deep Scan Support

The repository includes `PyMuPDF` for page rendering, but the deep scan path also requires `PaddleOCR` and `PaddlePaddle`.

Because Paddle packages are platform- and accelerator-specific, they are not locked into the base project dependencies. Install them into the active `uv` environment using the official Paddle instructions for your platform, then install `paddleocr`.

Typical flow:

```bash
uv sync --dev
# Install PaddlePaddle using the command recommended by the official Paddle docs for your CPU/GPU platform.
uv pip install paddleocr
```

References:

- PaddleOCR installation docs: https://www.paddleocr.ai/main/en/version3.x/installation.html
- PaddleOCR Python pipeline docs: https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html

## CLI Usage

```bash
uv run pdf-ocr-audit PATH [OPTIONS]
```

### Arguments

- `PATH`: A single PDF file or a directory containing PDF files.

### Options

- `--recursive`: Walk subdirectories when `PATH` is a directory.
- `--min-chars INTEGER`: Minimum extracted alphanumeric characters required for a page to pass. Default: `10`.
- `--format {text,json}`: Output format. Default: `text`.
- `--output PATH`: Write the report to a file instead of stdout.
- `--show-all-pages`: Include passing pages in text output.
- `--deep-scan`: Re-render each page and compare the embedded text layer against `PaddleOCR`.
- `--deep-scan-lang TEXT`: PaddleOCR language code for deep scan mode. Default: `en`.
- `--deep-scan-dpi INTEGER`: Rasterization DPI for deep scan mode. Default: `200`.
- `--deep-min-confidence FLOAT`: Minimum average PaddleOCR confidence for a deep scan page pass. Default: `0.70`.
- `--deep-min-similarity FLOAT`: Minimum text similarity between the embedded text layer and fresh OCR output. Default: `0.75`.

## Exit Codes

- `0`: Every audited page met the OCR threshold.
- `1`: One or more pages were missing sufficient OCR text or failed deep scan comparison thresholds.
- `2`: Operational problem such as no PDFs found or an unreadable/encrypted PDF.

## Example Text Output

```text
OCR audit summary
  Target: /data/pdfs
  PDFs scanned: 3
  Pages scanned: 12
  Pages passing: 10
  Pages failing: 2
  Files passing: 2
  Files failing: 1
  Errors: 0

Failing PDFs
- invoices/march.pdf
  page 2: missing OCR text (chars=0, words=0)
  page 3: deep scan mismatch (chars=128, words=24, snippet="Scanned text layer", deep_status=mismatch, reocr_chars=133, similarity=0.48, confidence=0.91, deep_snippet="fresh paddleocr output")
```

## Development

### Common Commands

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run bandit -q -r src
uv run pdf-ocr-audit /path/to/pdfs --recursive
uv run pdf-ocr-audit /path/to/pdfs --recursive --deep-scan
uv lock
```

### Quality Checks

This repository ships with a local and CI quality baseline:

- `ruff check .`: linting, bug-prone pattern detection, and import ordering
- `ruff format --check .`: formatting verification
- `pyright`: static type checking for the package
- `pytest`: unit tests, CLI tests, and coverage enforcement at `90%`
- `bandit -q -r src`: Python security linting for source code
- `pip-audit`: dependency vulnerability audit in the GitHub security workflow
- deep scan logic is unit-tested with fake runtimes; live `PaddleOCR` integration is documented but not exercised in CI

### Pre-commit Hooks

Install the local hooks once:

```bash
uv run pre-commit install --install-hooks
uv run pre-commit install --hook-type pre-push
```

Run them across the repository at any time:

```bash
uv run pre-commit run --all-files
```

### GitHub Actions

The repository includes two workflows:

- `CI`: runs lint, format, typing, tests, CLI smoke checks, and package builds on Python `3.11`, `3.12`, and `3.13`
- `Security`: runs `bandit` on source code and `pip-audit` on dependencies on `main`, on a weekly schedule, and on manual dispatch

### Dependabot

The repository also includes Dependabot configuration for:

- `uv` dependency updates from the root `pyproject.toml` / `uv.lock`
- GitHub Actions version updates under `.github/workflows/`

Both are scheduled weekly and grouped to reduce PR noise.

### Project Layout

- `src/pdf_ocr_audit/`: package source
- `tests/`: unit tests
- `AGENTS.md`: contributor and coding-agent guidance

## Limitations

- The tool verifies the presence of extractable text, not the semantic accuracy of OCR.
- Some PDFs contain text objects that are not meaningful OCR output. Tune `--min-chars` when needed.
- Password-protected PDFs are treated as errors unless they can be opened without a password.
- Deep scan is still a proxy for OCR accuracy. It compares embedded text to a second OCR pass; it is not a ground-truth benchmark.
