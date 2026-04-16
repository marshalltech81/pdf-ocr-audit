# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added a repository `SECURITY.md` policy that points reporters to GitHub private
  vulnerability reporting.

## [0.1.0] - 2026-04-16

### Added

- Initial CLI for auditing PDFs page-by-page for extractable OCR text coverage.
- Text and JSON reports with stable run, file, and page-level result data.
- Optional deep scan mode that re-renders pages and compares embedded text against
  PaddleOCR output.
- GitHub Actions workflows for CI, security checks, and tag-driven GitHub releases.
- Dependabot configuration for `uv` dependencies and GitHub Actions updates.

### Security

- AES-encrypted PDFs are classified cleanly through the bundled `cryptography`
  dependency.
- GitHub repository security features are enabled for code scanning, secret
  scanning, push protection, Dependabot alerts, Dependabot security updates, and
  private vulnerability reporting.
