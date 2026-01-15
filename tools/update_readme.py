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
    tree_str = "```text\n.\n"
    for root, dirs, files in os.walk(startpath):
        level = root.replace(startpath, "").count(os.sep)
        indent = "│   " * (level)
        subindent = "│   " * (level + 1)

        # Filter hidden directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d != "venv" and d != "__pycache__"
        ]

        if root != startpath:
            tree_str += f"{indent}├── {os.path.basename(root)}/\n"

        for f in files:
            if not f.startswith("."):
                tree_str += f"{subindent}├── {f}\n"

    tree_str += "```"
    return tree_str


def update_readme():
    """
    Updates the README.md file with the generated project structure.
    """
    tree = generate_tree(".")
    readme_path = "README.md"

    if os.path.exists(readme_path):
        # In a real implementation, we would read the file here and replace
        # the section between markers. For now, we just print the tree.
        print("Generated Tree Structure:")
        print(tree)
    else:
        print("README.md not found.")


if __name__ == "__main__":
    update_readme()
