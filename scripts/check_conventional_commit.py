"""Validate Conventional Commit subjects from messages, files, or a git range.

Used by the Conventional Commits CI check. It needs only the standard library and git, so it runs
without installing the project.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess  # nosec B404
import sys
from collections.abc import Iterable
from pathlib import Path

ALLOWED_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)

CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r"^(?P<type>" + "|".join(ALLOWED_TYPES) + r")"
    r"(\([a-z0-9._/-]+\))?"
    r"(!)?"
    r": "
    r"(?P<description>\S.*)$"
)


def validate_messages(messages: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for message in messages:
        subject = message.strip()
        if not subject:
            errors.append("Encountered an empty commit subject.")
        elif CONVENTIONAL_COMMIT_PATTERN.match(subject) is None:
            errors.append(
                f"Invalid Conventional Commit subject: {subject!r}. "
                f"Expected '<type>[(optional-scope)][!]: description' "
                f"where type is one of: {', '.join(ALLOWED_TYPES)}."
            )
    return errors


def read_commit_subjects_from_range(revision_range: str) -> list[str]:
    rev = r"[A-Za-z0-9][A-Za-z0-9._/\-^]*"
    if not re.fullmatch(rf"{rev}\.\.{rev}", revision_range):
        raise ValueError(f"Unsafe git revision range: {revision_range!r}")

    git_executable = shutil.which("git")
    if not git_executable:
        raise RuntimeError("git executable not found on PATH")

    try:
        completed = subprocess.run(
            [git_executable, "log", "--format=%s", revision_range],
            check=True,
            capture_output=True,
            text=True,
        )  # nosec B603
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise RuntimeError(
            f"git log failed for range {revision_range!r}" + (f": {stderr}" if stderr else "")
        ) from exc
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional commit message files, such as the path passed by a commit-msg hook.",
    )
    parser.add_argument(
        "--message",
        action="append",
        default=[],
        help="Explicit message to validate. May be passed multiple times.",
    )
    parser.add_argument(
        "--range",
        dest="revision_range",
        help="Git revision range to inspect, for example abc123..def456.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    messages = list(args.message)
    for path_str in args.paths:
        path = Path(path_str)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            print(f"Error: could not read commit message file {path}: {exc}", file=sys.stderr)
            return 1
        messages.append(lines[0].strip() if lines else "")

    if args.revision_range:
        try:
            messages.extend(read_commit_subjects_from_range(args.revision_range))
        except (ValueError, RuntimeError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if not messages:
        parser.error("provide at least one commit message source")

    errors = validate_messages(messages)
    if errors:
        print("Conventional Commit validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(messages)} conventional commit message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
