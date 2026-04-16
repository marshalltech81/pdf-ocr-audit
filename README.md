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
uv run mypy src
uv run bandit -q -r src
uv run pdf-ocr-audit /path/to/pdfs --recursive
uv run pdf-ocr-audit /path/to/pdfs --recursive --deep-scan
uv lock
```

### Quality Checks

This repository ships with a local and CI quality baseline:

- `ruff check .`: linting, bug-prone pattern detection, and import ordering
- `ruff format --check .`: formatting verification
- `mypy src`: static type checking for the package
- `pytest`: unit tests, CLI tests, and coverage enforcement at `90%`
- `bandit -q -r src`: Python security linting for source code
- `uv build`: verifies the package can build cleanly
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

The repository includes three workflows:

- `CI`: runs lint, format, typing, tests, CLI smoke checks, and package builds on Python `3.11`, `3.12`, and `3.13`
- `Security`: runs `bandit` on source code and `pip-audit` on dependencies on `main`, on a weekly schedule, and on manual dispatch
- `Release`: runs quality checks on pushed version tags, builds distributions, and creates a GitHub Release using the matching `CHANGELOG.md` section

### Dependabot

The repository also includes Dependabot configuration for:

- `uv` dependency updates from the root `pyproject.toml` / `uv.lock`
- GitHub Actions version updates under `.github/workflows/`

Both are scheduled weekly and grouped to reduce PR noise.

### Release Process

This repository uses a lightweight changelog-first release flow:

1. Add user-visible changes to the `Unreleased` section in `CHANGELOG.md`.
2. When cutting a release, move those entries into a new versioned section such as `## [0.2.0] - 2026-04-16`.
3. Bump `version` in `pyproject.toml` to match the release version.
4. Run the full local quality bar:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run bandit -q -r src
uv build
```

5. Open and merge a release PR with the version bump and changelog updates.
6. Create and push a matching tag from the merged commit on `main`:

```bash
git switch main
git pull --rebase origin main
git tag v0.2.0
git push origin v0.2.0
```

7. The `Release` workflow validates that the tag matches `pyproject.toml`, builds `dist/*`, and creates a GitHub Release whose body comes from the matching `CHANGELOG.md` section.

The current release automation creates GitHub Releases and build artifacts, but it does not publish to PyPI.

Prefer commit messages and PR titles that follow the Conventional Commits 1.0.0 specification:
https://www.conventionalcommits.org/en/v1.0.0/#specification

### Repository Security Features

The GitHub repository is configured to use:

- Dependabot alerts
- Dependabot security updates
- code scanning default setup
- private vulnerability reporting
- secret scanning
- push protection

### Project Layout

- `src/pdf_ocr_audit/`: package source
- `tests/`: unit tests
- `scripts/extract_changelog.py`: helper for tag-driven release notes
- `CHANGELOG.md`: release history and unreleased change queue
- `AGENTS.md`: contributor and coding-agent guidance
- `CLAUDE.md`: shim that points contributors back to `AGENTS.md`

## Limitations

- The tool verifies the presence of extractable text, not the semantic accuracy of OCR.
- Some PDFs contain text objects that are not meaningful OCR output. Tune `--min-chars` when needed.
- AES-encrypted PDFs rely on the bundled `cryptography` dependency so the audit can determine whether the file opens without a password.
- Password-protected PDFs are treated as errors unless they can be opened without a password.
- Deep scan is still a proxy for OCR accuracy. It compares embedded text to a second OCR pass; it is not a ground-truth benchmark.
