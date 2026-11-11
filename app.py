"""Launcher (used by the right-click menu):  pythonw app.py [--crush] FILE"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crusher.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
