"""Conftest for backtesting tests — adds standalone service to sys.path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "services" / "backtesting" / "src"))
