"""Shared helper for example scripts: load the example portfolio builder.

Numbered example filenames (``01_...py``) aren't valid Python module names,
so this loads ``06_build_portfolio.py`` by file path instead of by import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from options_risk.portfolio import Portfolio


def load_build_example_portfolio():  # noqa: ANN201
    module_path = Path(__file__).resolve().parent / "06_build_portfolio.py"
    spec = importlib.util.spec_from_file_location("build_portfolio_example", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.build_example_portfolio


def build_example_portfolio() -> Portfolio:
    return load_build_example_portfolio()()
