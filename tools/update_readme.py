import sys
import re
import os

def update_readme(min_version, max_version):
    readme_path = 'README.md'
    if not os.path.exists(readme_path):
        print(f"Error: {readme_path} not found.")
        return

    with open(readme_path, 'r') as f:
        content = f.read()

    # Regex to find "Python 3.x+" or similar patterns and replace/add version info
    # We look for the Prerequisites section
    pattern = r"(## Prerequisites\n\n\* Python )[\d\.]+(\+?)"
    replacement = f"\\1{min_version} - {max_version}"
    
    new_content = re.sub(pattern, replacement, content)
    
    # Also look for a badge if it exists, or just the text
    # If the pattern wasn't found (maybe it's formatted differently), we try a broader search
    if new_content == content:
         pattern = r"(Python )[\d\.]+(\+)"
         new_content = re.sub(pattern, f"Python {min_version} - {max_version}", content)

    with open(readme_path, 'w') as f:
        f.write(new_content)
    
    print(f"Updated README.md with Python versions: {min_version} - {max_version}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python update_readme_versions.py <min_version> <max_version>")
        sys.exit(1)
    
    min_ver = sys.argv[1]
    max_ver = sys.argv[2]
    update_readme(min_ver, max_ver)
