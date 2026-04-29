"""Utilities for processing and canonicalizing participant tags."""


def canonicalize_tags(val: str) -> set[str]:
    """Extracts unique characters as tags, ignoring whitespace and commas.

    Args:
        val: The raw tag string from a participant record.

    Returns:
        A set of unique single-character tag strings.
    """
    if not val or not isinstance(val, str):
        return set()
    return {c for c in val if not c.isspace() and c != ","}
