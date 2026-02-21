"""Conftest for backtesting tests — adds standalone service and project root to sys.path."""

import sys
from pathlib import Path

# Add project root so grid_backtester shims can import from bot.strategies.grid
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "services" / "backtesting" / "src")
)
