from __future__ import annotations

import re

WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(raw_text: str) -> str:
    return WHITESPACE_RE.sub(" ", raw_text).strip()


def count_alphanumeric_characters(text: str) -> int:
    return sum(character.isalnum() for character in text)


def count_words(text: str) -> int:
    return sum(1 for token in text.split(" ") if any(character.isalnum() for character in token))


def canonicalize_comparison_text(text: str) -> str:
    normalized_characters = [
        character.casefold() if character.isalnum() else " " for character in text
    ]
    return normalize_text("".join(normalized_characters))


def normalized_levenshtein_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0

    max_length = max(len(left), len(right))
    distance = levenshtein_distance(left, right)
    return max(0.0, 1.0 - (distance / max_length))


def levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous_row = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current_row = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            insertion_cost = current_row[right_index - 1] + 1
            deletion_cost = previous_row[right_index] + 1
            substitution_cost = previous_row[right_index - 1] + (left_character != right_character)
            current_row.append(min(insertion_cost, deletion_cost, substitution_cost))
        previous_row = current_row
    return previous_row[-1]
