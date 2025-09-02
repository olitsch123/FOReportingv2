"""Quick start script for FOReporting v2."""

import subprocess
import sys
from pathlib import Path


def main():
    """Quick start the system."""
    print("🚀 FOReporting v2 - Quick Start")
    print("=" * 40)
    
    # Run the system startup script
    script_path = Path(__file__).parent / "scripts" / "run_system.py"
    
    try:
        subprocess.run([sys.executable, str(script_path)])
    except KeyboardInterrupt:
        print("\n✅ System stopped")


if __name__ == "__main__":
    main()