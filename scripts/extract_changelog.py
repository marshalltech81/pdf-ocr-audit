from __future__ import annotations

import argparse
import re
from pathlib import Path

SECTION_HEADER_RE = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - .+)?$")


def extract_release_notes(changelog_text: str, version: str) -> str:
    lines = changelog_text.splitlines()
    start_index: int | None = None

    for index, line in enumerate(lines):
        match = SECTION_HEADER_RE.match(line)
        if match and match.group("version") == version:
            start_index = index
            break

    if start_index is None:
        raise ValueError(f"Version not found in changelog: {version}")

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if SECTION_HEADER_RE.match(lines[index]):
            end_index = index
            break

    section = "\n".join(lines[start_index:end_index]).strip()
    if not section:
        raise ValueError(f"Changelog section is empty for version: {version}")
    return section


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract-changelog",
        description="Extract a single version section from CHANGELOG.md.",
    )
    parser.add_argument("version", help="Version to extract, without a leading v.")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to the changelog file. Default: CHANGELOG.md.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    changelog_text = args.changelog.read_text(encoding="utf-8")
    release_notes = extract_release_notes(changelog_text, args.version)
    print(release_notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
