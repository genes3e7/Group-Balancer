"""Utility script to update the Project Structure section in README.md.

Refactored for:
- Correct tree indentation (removed redundant | level).
- Dynamic README updates (badge and prerequisite version text).
- Professional logging and pathspec support.
"""

import logging
import os
import re
import sys

import pathspec

# Configure local logger
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("readme_tool")


def load_gitignore_spec(root_path: str) -> pathspec.PathSpec:
    """Loads .gitignore patterns and returns a PathSpec object.

    Args:
        root_path: The root directory of the project.

    Returns:
        A PathSpec object containing the patterns from .gitignore.
    """
    patterns = [".git/", "__pycache__/", "venv/", ".venv/", "artifacts/"]
    gitignore_path = os.path.join(root_path, ".gitignore")

    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def generate_tree(startpath: str, spec: pathspec.PathSpec) -> str:
    """Generates a string representation of the file tree.

    Args:
        startpath: The directory to start the tree from.
        spec: PathSpec object to filter out ignored files.

    Returns:
        A string representing the file tree in markdown code block.
    """
    tree_lines = ["```text", "."]

    # Use a recursive approach for cleaner indentation logic
    def walk_dir(path, prefix=""):
        # Get relative path for matching
        rel_path = os.path.relpath(path, startpath)

        # List items and filter
        try:
            items = sorted(os.listdir(path))
        except PermissionError:
            return

        # Filter items using pathspec
        valid_items = []
        for item in items:
            item_path = os.path.join(rel_path, item) if rel_path != "." else item
            # Pathspec expects directory patterns to end with /
            if os.path.isdir(os.path.join(path, item)):
                check_path = item_path + "/"
            else:
                check_path = item_path

            if not spec.match_file(check_path):
                valid_items.append(item)

        for i, item in enumerate(valid_items):
            full_path = os.path.join(path, item)
            is_last = i == len(valid_items) - 1
            connector = "└── " if is_last else "├── "

            display_name = item + "/" if os.path.isdir(full_path) else item
            tree_lines.append(f"{prefix}{connector}{display_name}")

            if os.path.isdir(full_path) and not os.path.islink(full_path):
                extension = "    " if is_last else "│   "
                walk_dir(full_path, prefix + extension)

    walk_dir(startpath)
    tree_lines.append("```")
    return "\n".join(tree_lines)


def update_readme(min_ver: str | None = None, max_ver: str | None = None) -> None:
    """Updates README.md with generated tree and dynamic version info.

    Args:
        min_ver: Minimum supported Python version.
        max_ver: Maximum supported Python version.
    """
    spec = load_gitignore_spec(".")
    tree = generate_tree(".", spec)
    readme_path = "README.md"

    if not os.path.exists(readme_path):
        logger.error(f"{readme_path} not found.")
        return

    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    # 1. Update Tree
    start_marker = "<!-- PROJECT_TREE_START -->"
    end_marker = "<!-- PROJECT_TREE_END -->"
    if start_marker in content and end_marker in content:
        pattern = re.compile(
            f"{re.escape(start_marker)}.*?{re.escape(end_marker)}", re.DOTALL
        )
        content = pattern.sub(f"{start_marker}\n{tree}\n{end_marker}", content)
        logger.info("Updated project tree.")

    # 2. Update Version Badge
    if min_ver and max_ver:
        # Matches badge URL part: python-3.10%20-%203.14-blue
        badge_pattern = re.compile(r"python-3\.[0-9]+[^\s\[\]\(\)]*-blue")
        new_badge_url = f"python-{min_ver}%20-%20{max_ver}-blue"
        content = badge_pattern.sub(new_badge_url, content)

        # Also update the Alt Text of the badge: [Python 3.10 - 3.14]
        alt_pattern = re.compile(
            r"\[Python 3\.[0-9]+(?:-[^\]]+)?\s*-\s*3\.[0-9]+(?:-[^\]]+)?\]"
        )
        new_alt = f"[Python {min_ver} - {max_ver}]"
        content = alt_pattern.sub(new_alt, content)

        # 3. Update Prerequisite Text (e.g., "Python 3.10 or higher")
        prereq_pattern = re.compile(r"Python 3\.[0-9]+ or higher")
        new_prereq = f"Python {min_ver} or higher"
        content = prereq_pattern.sub(new_prereq, content)

        msg = f"Updated Python versions to {min_ver}-{max_ver} in badges/text."
        logger.info(msg)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    m_ver = sys.argv[1] if len(sys.argv) > 1 else None
    x_ver = sys.argv[2] if len(sys.argv) > 2 else None
    update_readme(m_ver, x_ver)
