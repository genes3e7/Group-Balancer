"""
Utility script to update the Project Structure section in README.md.

This script scans the project directory and generates a tree-like text
structure, then injects it into the README file between designated markers.
It respects patterns defined in .gitignore to exclude unwanted files.
"""

import os
import fnmatch


def load_gitignore_patterns(startpath: str) -> list[str]:
    """
    Loads ignore patterns from the .gitignore file in the startpath.
    Also includes some default system/IDE ignores.

    Args:
        startpath (str): The root directory to look for .gitignore.

    Returns:
        list[str]: A list of patterns to ignore.
    """
    # Default ignores to ensure clean output even without .gitignore
    patterns = [".git", "__pycache__", ".DS_Store", "venv", ".venv", ".idea", ".vscode"]
    
    gitignore_path = os.path.join(startpath, ".gitignore")
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def should_ignore(name: str, is_dir: bool, patterns: list[str]) -> bool:
    """
    Checks if a file or directory name matches any of the ignore patterns.

    Args:
        name (str): The name of the file or directory.
        is_dir (bool): True if the name refers to a directory.
        patterns (list[str]): List of ignore patterns (glob style).

    Returns:
        bool: True if the item should be ignored, False otherwise.
    """
    for pattern in patterns:
        # Handle directory-specific patterns (ending with /)
        if pattern.endswith("/"):
            if is_dir:
                # Remove trailing slash for matching directory name
                # E.g. "artifacts/" matches directory "artifacts"
                if fnmatch.fnmatch(name, pattern.rstrip("/")):
                    return True
        else:
            # Handle general file/name patterns
            # E.g. "*.pyc" matches "file.pyc"
            if fnmatch.fnmatch(name, pattern):
                return True
    return False


def generate_tree(startpath: str) -> str:
    """
    Generates a string representation of the file tree.

    Args:
        startpath (str): Root directory to scan.

    Returns:
        str: Formatted file tree string.
    """
    tree_lines = ["```text", "."]
    
    # Load ignore patterns once
    patterns = load_gitignore_patterns(startpath)

    # Walk the tree
    for root, dirs, files in os.walk(startpath):
        # 1. Filter Directories IN-PLACE
        # This prevents os.walk from entering ignored directories (like venv or artifacts)
        # and removes them from the generated tree.
        dirs[:] = [d for d in dirs if not should_ignore(d, True, patterns)]
        
        # Sort for consistent output
        dirs.sort()
        files.sort()

        # 2. Filter Files
        # Create a new list containing only non-ignored files
        files = [f for f in files if not should_ignore(f, False, patterns)]

        # Use relpath for robust level calculation
        try:
            rel_path = os.path.relpath(root, startpath)
            level = rel_path.count(os.sep)
        except ValueError:
            level = 0

        if root == startpath:
            level = 0
        else:
            level += 1

        indent = "│   " * level

        if root != startpath:
            tree_lines.append(f"{indent}├── {os.path.basename(root)}/")

        subindent = "│   " * (level + 1)
        for i, f in enumerate(files):
            # Use '└──' if it's the last file and no subdirectories follow
            connector = "└──" if i == len(files) - 1 and not dirs else "├──"
            tree_lines.append(f"{subindent}{connector} {f}")

    tree_lines.append("```")
    return "\n".join(tree_lines)


def update_readme():
    """
    Updates the README.md file with the generated project structure.
    """
    tree = generate_tree(".")
    readme_path = "README.md"
    # Concrete markers defined to prevent logic errors during split
    start_marker = "<!-- PROJECT_TREE_START -->"
    end_marker = "<!-- PROJECT_TREE_END -->"

    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        if (
            start_marker
            and end_marker
            and start_marker in content
            and end_marker in content
        ):
            # Replace the content between markers
            pre = content.split(start_marker)[0]
            post = content.split(end_marker)[1]
            new_content = f"{pre}{start_marker}\n{tree}\n{end_marker}{post}"

            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("Successfully updated README.md with new project structure.")
        else:
            print("Markers not found. Appending tree to end of file.")
            with open(readme_path, "a", encoding="utf-8") as f:
                f.write(
                    f"\n## Project Structure\n\n{start_marker}\n{tree}\n{end_marker}\n"
                )
    else:
        print("README.md not found. Creating new file.")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                f"# Project\n\n## Project Structure\n\n{start_marker}\n{tree}\n{end_marker}\n"
            )


if __name__ == "__main__":
    update_readme()
