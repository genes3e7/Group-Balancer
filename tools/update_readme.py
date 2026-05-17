"""Utility script to update the Project Structure section in README.md.

Refactored for:
- Correct tree indentation (removed redundant | level).
- Dynamic README updates (badge and prerequisite version text).
- Professional logging and error handling.
"""

import logging
import re
import sys
from pathlib import Path

# Configure logging for the update tool
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("readme_update")


def get_project_tree(root_path: Path) -> str:
    """Generates a text-based project directory tree.

    Args:
        root_path (Path): The absolute path to the project root.

    Returns:
        str: A formatted string representing the directory tree.
    """
    ignore_patterns = _load_ignore_patterns(root_path)
    tree_lines = ["."]

    def walk_dir(path: Path, prefix: str = "", current_rel: str = ".") -> None:
        """Recursive helper to build the tree lines."""
        try:
            items = sorted(path.iterdir())
        except PermissionError:
            return

        valid_items = _filter_items(items, current_rel, ignore_patterns)

        for i, full_path in enumerate(valid_items):
            is_last = i == len(valid_items) - 1
            _append_tree_line(tree_lines, full_path, prefix, is_last)

            if full_path.is_dir() and not full_path.is_symlink():
                extension = "    " if is_last else "│   "
                new_rel = (
                    f"{current_rel}/{full_path.name}"
                    if current_rel != "."
                    else full_path.name
                )
                walk_dir(full_path, prefix + extension, current_rel=new_rel)

    walk_dir(root_path)
    return "\n".join(tree_lines)


def _load_ignore_patterns(root_path: Path) -> list[str]:
    """Loads ignore patterns from .gitignore and defaults."""
    patterns = [
        ".git/",
        "__pycache__/",
        "venv/",
        ".venv/",
        "artifacts/",
        ".pytest_cache/",
        ".ruff_cache/",
        "build/",
        "dist/",
        ".coverage",
    ]
    gitignore_path = root_path / ".gitignore"

    if gitignore_path.exists():
        with gitignore_path.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # Preserve original pattern (don't force trailing slash)
                    patterns.append(stripped)
    return patterns


def _filter_items(
    items: list[Path], current_rel: str, ignore_patterns: list[str]
) -> list[Path]:
    """Filters directory items based on ignore patterns."""
    valid = []
    for item in items:
        item_rel = f"{current_rel}/{item.name}" if current_rel != "." else item.name
        check_path = item_rel + "/" if item.is_dir() else item_rel

        should_ignore = False
        for p in ignore_patterns:
            # Handle directory-only patterns (ending in /)
            if p.endswith("/"):
                if check_path.startswith(p) or check_path == p.rstrip("/"):
                    should_ignore = True
                    break
            # Handle file or exact patterns
            elif item_rel == p or item_rel.startswith(f"{p}/"):
                should_ignore = True
                break

        if not should_ignore:
            valid.append(item)
    return valid


def _append_tree_line(
    tree_lines: list[str], path: Path, prefix: str, is_last: bool
) -> None:
    """Formats and appends a single line to the tree."""
    connector = "└── " if is_last else "├── "
    display_name = path.name

    if path.is_symlink():
        target = path.readlink()
        display_name = f"{path.name} -> {target}"
    elif path.is_dir():
        display_name = f"{path.name}/"

    tree_lines.append(f"{prefix}{connector}{display_name}")


def update_readme(min_ver: str | None = None, max_ver: str | None = None) -> None:
    """Inserts the project tree and updates versions in README.md.

    Args:
        min_ver (str | None): Minimum Python version for badges.
        max_ver (str | None): Maximum Python version for badges.
    """
    readme_path = Path("README.md")

    if not readme_path.exists():
        logger.error("%s not found.", readme_path)
        sys.exit(1)

    with readme_path.open(encoding="utf-8") as f:
        content = f.read()

    start_marker = "<!-- PROJECT_TREE_START -->"
    end_marker = "<!-- PROJECT_TREE_END -->"

    if start_marker not in content or end_marker not in content:
        logger.error(
            "Missing markers '%s' or '%s' in %s.",
            start_marker,
            end_marker,
            readme_path,
        )
        sys.exit(1)

    # 1. Update Project Tree
    tree = get_project_tree(Path.cwd())
    pattern = re.compile(
        f"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL
    )
    replacement = f"{start_marker}\n\n```text\n{tree}\n```\n\n{end_marker}"
    content = pattern.sub(replacement, content)

    # 2. Update Version Badge
    if min_ver and max_ver:
        content = _update_badges(content, min_ver, max_ver)

    with readme_path.open("w", encoding="utf-8") as f:
        f.write(content)


def _update_badges(content: str, min_ver: str, max_ver: str) -> str:
    """Internal helper to update Python version badges and text."""
    # Matches badge URL part: Python-3.11--3.14-blue (case-insensitive)
    badge_pattern = re.compile(r"Python-\d+\.\d+--\d+\.\d+-blue", re.IGNORECASE)
    new_badge_url = f"Python-{min_ver}--{max_ver}-blue"
    content = badge_pattern.sub(new_badge_url, content)

    # Also update the Alt Text of the badge: [Python: 3.11-3.14]
    alt_pattern = re.compile(
        r"\[Python:?\s*\d+\.\d+\s*(?:-|through|to|--)\s*\d+\.\d+\]",
        re.IGNORECASE,
    )
    new_alt = f"[Python: {min_ver}-{max_ver}]"
    content = alt_pattern.sub(new_alt, content)

    # 3. Update Prerequisite Text (if any exists in a standard format)
    prereq_pattern = re.compile(
        r"Python \d+\.\d+(?:-[A-Za-z0-9.]+)?(?:\s*(?:through|to|-|or higher|--)\s*"
        r"\d+\.\d+(?:-[A-Za-z0-9.]+)?\.?|\s+or\s+higher)",
        re.IGNORECASE,
    )
    new_prereq = f"Python {min_ver} through {max_ver}"
    content = prereq_pattern.sub(new_prereq, content)

    msg = f"Updated Python versions to {min_ver}-{max_ver} in badges/text."
    logger.info(msg)
    return content


if __name__ == "__main__":
    # Command line arguments for Python version range in badges
    MIN_ARG_IDX = 1
    MAX_ARG_IDX = 2

    m_ver = sys.argv[MIN_ARG_IDX] if len(sys.argv) > MIN_ARG_IDX else None
    x_ver = sys.argv[MAX_ARG_IDX] if len(sys.argv) > MAX_ARG_IDX else None
    update_readme(m_ver, x_ver)
