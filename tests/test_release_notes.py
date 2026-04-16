from __future__ import annotations

import pytest

from scripts.extract_changelog import extract_release_notes


def test_extract_release_notes_returns_requested_version_section() -> None:
    changelog = """# Changelog

## [Unreleased]

### Added

- Pending work.

## [0.2.0] - 2026-04-16

### Added

- New release feature.

### Fixed

- Release bug fix.

## [0.1.0] - 2026-04-15

### Added

- Initial release.
"""

    release_notes = extract_release_notes(changelog, "0.2.0")

    assert (
        release_notes
        == """## [0.2.0] - 2026-04-16

### Added

- New release feature.

### Fixed

- Release bug fix."""
    )


def test_extract_release_notes_raises_when_version_is_missing() -> None:
    with pytest.raises(ValueError, match="Version not found"):
        extract_release_notes("# Changelog\n", "9.9.9")
