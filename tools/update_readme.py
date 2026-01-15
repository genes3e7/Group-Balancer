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
                # Skip comments and negation patterns (simple implementation)
                # Negation patterns (starting with !) are currently ignored/skipped
                # rather than implemented logic-wise.
                if line and not line.startswith("#") and not line.startswith("!"):
                    patterns.append(line)
    return patterns


def should_ignore(name: str, is_dir: bool, patterns: list[str]) -> bool:
    """
    Checks if a file or directory name matches any of the ignore patterns.

    Note:
        This implementation primarily matches against the file/directory basename.
        Complex path-based patterns (e.g. 'foo/bar' or '**/*.log') are not 
        fully supported by simple fnmatch on the basename.

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
            # If root is startpath, rel_path is '.', count of sep is 0
            if rel_path == ".":
                level = 0
            else:
                level = rel_path.count(os.sep) + 1
        except ValueError:
            level = 0

        indent = "│   " * level

        if root != startpath:
            # Note: Connectors for directories are simplified here.
            tree_lines.append(f"{indent}├── {os.path.basename(root)}/")

        subindent = "│   " * (level + 1)
        for i, f in enumerate(files):
            # Use '└──' if it's the last file and no subdirectories follow in this folder
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

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        # Check for duplicate markers
        if content.count(start_marker) > 1 or content.count(end_marker) > 1:
            print(f"Error: Multiple occurrences of markers found in {readme_path}. Please resolve manually.")
            return

        # Validate existence and correct order
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Safe slicing using validated indices
            pre = content[:start_idx]
            post = content[end_idx + len(end_marker):]
            
            new_content = f"{pre}{start_marker}\n{tree}\n{end_marker}{post}"

            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("Successfully updated README.md with new project structure.")
        
        else:
            if start_idx != -1 and end_idx != -1 and start_idx > end_idx:
                print(f"Error: Markers found but in wrong order (END before START) in {readme_path}.")
                return
            
            # Warn about orphaned markers to prevent corruption
            if start_idx != -1 and end_idx == -1:
                print(f"Warning: START marker found without END marker in {readme_path}.")
                return
            elif end_idx != -1 and start_idx == -1:
                print(f"Warning: END marker found without START marker in {readme_path}.")
                return

            print("Markers not found or invalid. Appending tree to end of file.")
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
