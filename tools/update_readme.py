import sys
import re
import os

def update_readme(min_version, max_version):
    readme_path = 'README.md'
    if not os.path.exists(readme_path):
        print(f"Error: {readme_path} not found.")
        sys.exit(1)

    with open(readme_path, 'r') as f:
        content = f.read()

    version_string = f"{min_version} - {max_version}"
    print(f"Updating README to support Python: {version_string}")

    # Regex for "* Python ..." line
    pattern = r"(\* Python ).*"
    
    if not re.search(pattern, content):
        # Fallback regex
        pattern = r"(Python )[\d\.]+(?: - [\d\.]+)?(?:\+)?"
        if not re.search(pattern, content):
             print("Critical: Could not find Python version definition in README.")
             sys.exit(1)

    # Use lambda to avoid backslash escaping issues in replacement string
    new_content = re.sub(pattern, lambda m: f"{m.group(1)}{version_string}", content)

    if new_content != content:
        with open(readme_path, 'w') as f:
            f.write(new_content)
        print("README.md updated successfully.")
    else:
        print("README.md already up to date.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python update_readme.py <min_version> <max_version>")
        sys.exit(1)
    
    update_readme(sys.argv[1], sys.argv[2])
