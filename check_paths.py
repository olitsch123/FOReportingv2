#!/usr/bin/env python3
"""Check file paths and encoding."""

import os
from pathlib import Path

def check_paths():
    """Check investor paths and their encoding."""
    print("=" * 60)
    print("Checking File Paths and Encoding")
    print("=" * 60)
    
    # Get environment variables
    investor1_path = os.getenv("INVESTOR1_PATH")
    investor2_path = os.getenv("INVESTOR2_PATH")
    
    print("\n1. Environment Variables (raw):")
    print(f"   INVESTOR1_PATH: {repr(investor1_path)}")
    print(f"   INVESTOR2_PATH: {repr(investor2_path)}")
    
    print("\n2. Path Existence Check:")
    paths = [
        ("Investor 1", investor1_path),
        ("Investor 2", investor2_path)
    ]
    
    for name, path_str in paths:
        if path_str:
            print(f"\n   {name}:")
            print(f"   Raw path: {path_str}")
            
            try:
                path = Path(path_str)
                exists = path.exists()
                print(f"   Exists: {exists}")
                
                if exists:
                    # Count files
                    extensions = ['.pdf', '.xlsx', '.xls', '.csv', '.txt', '.docx']
                    total_files = 0
                    
                    for ext in extensions:
                        files = list(path.rglob(f"*{ext}"))
                        if files:
                            print(f"   - {ext}: {len(files)} files")
                            total_files += len(files)
                    
                    print(f"   Total supported files: {total_files}")
                    
                    # Show first few files
                    all_files = []
                    for ext in extensions:
                        all_files.extend(list(path.rglob(f"*{ext}"))[:3])
                    
                    if all_files:
                        print(f"\n   Sample files:")
                        for f in all_files[:5]:
                            print(f"   - {f.name}")
                else:
                    print("   ⚠️  Path does not exist!")
                    
                    # Try to debug the path
                    parts = path.parts
                    print(f"   Path parts: {parts}")
                    
                    # Check each part
                    current = Path(parts[0])
                    for part in parts[1:]:
                        current = current / part
                        if not current.exists():
                            print(f"   ✗ Not found at: {current}")
                            break
                        else:
                            print(f"   ✓ Exists: {current}")
                            
            except Exception as e:
                print(f"   Error: {e}")
        else:
            print(f"\n   {name}: Not configured")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    # Ensure UTF-8 output
    import sys
    if sys.platform == "win32":
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')
    
    check_paths()