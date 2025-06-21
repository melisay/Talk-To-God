#!/usr/bin/env python3
"""
AI Assistant Project - Local Version Entry Point
Run this script from the root directory to start the local version.
"""

import os
import sys
from pathlib import Path
from asyncio import run

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the local version
from local.main import AIAssistant

if __name__ == "__main__":
    try:
        print("Starting AI Assistant (Local Version)...")
        assistant = AIAssistant()
        run(assistant.run())
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) 