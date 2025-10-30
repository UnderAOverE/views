import subprocess
import json
import sys
import os

def check_pipdeptree_installed():
    """Checks if pipdeptree is installed."""
    try:
        subprocess.run([sys.executable, "-m", "pipdeptree", "--version"], 
                       capture_output=True, check=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_pipdeptree():
    """Installs pipdeptree if it's not present."""
    print("pipdeptree is not installed. Installing it now...")
    try:
        # Use sys.executable to ensure pip corresponds to the current venv
        subprocess.run([sys.executable, "-m", "pip", "install", "pipdeptree"], 
                       check=True, text=True, capture_output=True)
        print("pipdeptree installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install pipdeptree: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during pipdeptree installation: {e}")
        return False

def get_dependency_tree(package_name):
    """
    Fetches the dependency tree for a given package name using pipdeptree.
    Returns a dictionary representing the dependency tree.
    """
    try:
        # pipdeptree --json-tree provides a structured JSON output
        result = subprocess.run(
            [sys.executable, "-m", "pipdeptree", "--json-tree"],
            capture_output=True,
            check=True,
            text=True,
            encoding='utf-8' # Specify encoding for consistency
        )
        full_tree = json.loads(result.stdout)
        
        # Find the specific package in the full tree
        for pkg_node in full_tree:
            if pkg_node['package_name'].lower() == package_name.lower():
                return pkg_node
        return None # Package not found in the tree
        
    except subprocess.CalledProcessError as e:
        print(f"Error running pipdeptree: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from pipdeptree output: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while getting dependency tree: {e}")
        return None

def print_dependencies_recursive(node, indent=0, visited_packages=None):
    """
    Recursively prints dependencies with indentation.
    Uses visited_packages to prevent infinite loops for circular dependencies.
    """
    if visited_packages is None:
        visited_packages = set()

    package_info = f"{node['package_name']}=={node['installed_version']}"
    
    # Check for circular dependencies or already printed
    if package_info in visited_packages and indent > 0:
        print(f"{'  ' * indent}- {package_info} (circular dependency or already listed)")
        return
    
    print(f"{'  ' * indent}- {package_info}")
    visited_packages.add(package_info)

    for dep in node.get('dependencies', []):
        print_dependencies_recursive(dep, indent + 1, visited_packages)


def main():
    if len(sys.argv) < 2:
        print("Usage: python dependency_checker.py <library_name>")
        print("Example: python dependency_checker.py requests")
        sys.exit(1)

    library_name = sys.argv[1]

    # Check if we are in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Warning: You are not in an active virtual environment.")
        print("Dependencies will be checked against your global Python packages.")
        print("It's recommended to run this script within a virtual environment.")
        print("-" * 60)

    if not check_pipdeptree_installed():
        if not install_pipdeptree():
            print("Cannot proceed without pipdeptree. Exiting.")
            sys.exit(1)

    print(f"\nChecking dependencies for '{library_name}' in the current environment ({sys.prefix})...")
    
    tree_data = get_dependency_tree(library_name)

    if tree_data:
        print(f"\nDependency tree for '{library_name}':")
        print_dependencies_recursive(tree_data)
    else:
        print(f"'{library_name}' not found or no dependency information available in this environment.")
        print("Please ensure the library is installed in your active virtual environment.")

if __name__ == "__main__":
    main()
