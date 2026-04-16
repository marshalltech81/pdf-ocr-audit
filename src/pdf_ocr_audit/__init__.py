"""Tools for auditing whether PDFs contain extractable OCR text on every page."""

from .audit import audit_path
from .models import DeepScanConfig

__all__ = ["DeepScanConfig", "audit_path"]
