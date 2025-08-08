#!/usr/bin/env python3
"""
Fix import paths in all moved scripts.
This script updates sys.path additions to point to the project root correctly.
"""

import os
import re
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fix_imports_in_file(filepath):
    """Fix import paths in a single Python file"""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Skip if already has correct import
    if "project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))" in content:
        return False
    
    # Check if file has sys.path manipulation
    if "sys.path" in content:
        # Replace old sys.path.append with correct version
        old_pattern = r'sys\.path\.append\([^)]+\)'
        new_code = """# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)"""
        
        content = re.sub(old_pattern, new_code, content, count=1)
        
    elif "import sys" in content and "from src." in content:
        # Add sys.path configuration after import sys
        lines = content.split('\n')
        new_lines = []
        sys_import_found = False
        path_added = False
        
        for line in lines:
            new_lines.append(line)
            if not path_added and sys_import_found and (line.strip() == '' or line.startswith('from src.')):
                new_lines.insert(-1, "\n# Add project root to path")
                new_lines.insert(-1, "project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))")
                new_lines.insert(-1, "sys.path.insert(0, project_root)")
                path_added = True
            if "import sys" in line:
                sys_import_found = True
        
        content = '\n'.join(new_lines)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    return True

def main():
    """Fix imports in all Python scripts"""
    
    scripts_dir = os.path.join(project_root, "scripts")
    
    fixed_count = 0
    for root, dirs, files in os.walk(scripts_dir):
        for file in files:
            if file.endswith('.py') and file != 'fix_imports.py':
                filepath = os.path.join(root, file)
                if fix_imports_in_file(filepath):
                    fixed_count += 1
                    print(f"✅ Fixed: {filepath}")
    
    print(f"\n📊 Fixed {fixed_count} files")

if __name__ == "__main__":
    main()