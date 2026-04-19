# AGENTS.md

## Mission

This repository exists to answer one operational question reliably:

> Does every page in every target PDF have a usable extractable text layer that supports OCR-driven workflows?

Changes should preserve that focus. Prefer clear, audit-friendly behavior over cleverness.

## Repository Principles

- Keep the default toolchain Python-first and `uv`-native.
- Preserve deterministic CLI behavior so the tool is safe for local use, CI, and batch jobs.
- Treat missing OCR text as a content failure and unreadable PDFs as an operational failure.
- Make page-level failures easy to understand without opening the PDF manually.
- Keep dependencies lean. `pypdf` is the preferred parser unless there is a strong reason to add another backend.

## Current Architecture

- `src/pdf_ocr_audit/audit.py`: core PDF discovery and page-audit logic
- `src/pdf_ocr_audit/deep_scan.py`: optional deep verification mode using page rendering and PaddleOCR comparison
- `src/pdf_ocr_audit/reporting.py`: text and JSON rendering helpers
- `src/pdf_ocr_audit/cli.py`: argparse CLI and exit-code handling
- `src/pdf_ocr_audit/models.py`: shared dataclasses for page/file/run results
- `src/pdf_ocr_audit/text_utils.py`: normalization and text comparison helpers
- `tests/`: programmatic PDF fixtures and regression tests
- `.pre-commit-config.yaml`: local quality gates for contributors
- `.github/dependabot.yml`: automated dependency and GitHub Actions update policy
- `.github/workflows/ci.yml`: primary GitHub Actions validation workflow
- `.github/workflows/security.yml`: scheduled and on-demand security checks

## Behavioral Contracts

These are important and should not change casually:

- Default threshold: a page passes when extracted alphanumeric text count is `>= 10`.
- When deep scan mode is enabled, a page passes only if:
  - the embedded text layer meets the base threshold, and
  - the PaddleOCR comparison meets configured similarity and confidence thresholds
- Exit codes:
  - `0` means all audited pages passed.
  - `1` means at least one audited page failed OCR coverage.
  - `2` means the run could not be completed cleanly, such as no PDFs found or a read failure.
- Text output should prioritize failures first and remain readable in terminal logs.
- JSON output should stay stable and fully represent per-page outcomes.
- Encrypted or unreadable PDFs should not be silently skipped.

## Workflow Expectations

Use these commands unless the task specifically requires something else:

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run bandit -q -r src
uv build
uv lock
```

## Quality Bar

Changes are expected to keep these checks green:

- `ruff check .`
- `ruff format --check .`
- `pyright`
- `pytest` with coverage floor `>= 90%`
- `bandit -q -r src`
- `uv build`

`pip-audit` is part of the GitHub security workflow and may rely on network access that is not always available in local sandboxed runs.

Live PaddleOCR verification is intentionally not part of default CI because PaddlePaddle installation is platform-specific and heavyweight. Keep deep-scan behavior covered with unit tests that inject fake OCR runtimes, and document any manual validation you perform with a real Paddle environment.

Dependabot is configured for both `uv` and `github-actions`. When changing dependency layout or workflow locations, keep `.github/dependabot.yml` aligned so automated updates continue to work.

## Editing Guidance

- Use standard-library modules where they keep the code simple.
- Keep type hints throughout the package.
- Prefer small pure functions for normalization, counting, and rendering logic.
- Avoid burying CLI policy inside low-level audit functions.
- Do not commit large binary PDFs for tests unless absolutely necessary. Prefer generating fixtures in test code.
- Keep GitHub Actions workflows and local hooks aligned so contributors see the same failures locally and in CI.
- Keep the default scan path fast and dependency-light; deep scan should remain explicitly opt-in.

## When Adding Features

If you add a new option or report field:

- update the CLI help text
- update `README.md`
- add or adjust tests
- make sure type checks and coverage still pass
- preserve backwards-compatible JSON fields unless there is a deliberate versioning decision

If you change OCR heuristics:

- document the reasoning clearly
- add tests covering the old and new edge cases
- call out user-visible tradeoffs in `README.md`
- review whether the quality thresholds or smoke tests need adjustment

If you change deep scan behavior:

- keep failures explainable in text output
- preserve the helpful "missing text layer but re-OCR detected" distinction
- avoid requiring live Paddle downloads in unit tests

## Good Extensions

- CSV report output
- password handling for protected PDFs
- confidence bands such as "pass", "weak text", and "missing text"
- GitHub Action packaging for CI use

## Avoid

- silent skips
- hidden magic thresholds
- parser-specific behavior leaking into the CLI contract
- adding heavyweight OCR engines to this repository unless the scope explicitly changes from auditing to OCR generation
