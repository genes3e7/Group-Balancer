"""
Utility script to update the Project Structure section in README.md.

This script scans the project directory and generates a tree-like text
structure, then injects it into the README file between designated markers.
"""

import os


def generate_tree(startpath: str) -> str:
    """
    Generates a string representation of the file tree.

    Args:
        startpath (str): Root directory to scan.

    Returns:
        str: Formatted file tree string.
    """
    tree_lines = ["```text", "."]

    # Walk the tree
    for root, dirs, files in os.walk(startpath):
        # Sort for consistent output
        dirs.sort()
        files.sort()

        # Filter hidden directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d != "venv" and d != "__pycache__"
        ]
        files = [f for f in files if not f.startswith(".")]

        # Use relpath for robust level calculation, avoiding replacement issues
        try:
            level = os.path.relpath(root, startpath).count(os.sep)
        except ValueError:
            level = 0

        # Adjust level if root is same as startpath (relpath is '.')
        if root == startpath:
            level = 0
        else:
            # os.walk yields subdirectories; relpath calculation handles nesting depth
            # If root is "./src", level is 0 (assuming startpath is ".").
            # We want level based on depth relative to startpath.
            if os.path.relpath(root, startpath) == ".":
                level = 0
            else:
                level = os.path.relpath(root, startpath).count(os.sep) + 1

        indent = "│   " * level

        if root != startpath:
            tree_lines.append(f"{indent}├── {os.path.basename(root)}/")

        subindent = "│   " * (level + 1)
        for i, f in enumerate(files):
            # Use '└──' if it's the last file for aesthetics
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
