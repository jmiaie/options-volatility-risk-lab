"""Validation errors for the pricing package.

Inputs are validated explicitly so that malformed contracts (negative spot,
non-positive strike, negative volatility, negative time) raise a clear error
instead of silently propagating NaN through downstream Greeks, IV solves, or
portfolio aggregation.
"""

from __future__ import annotations


class OptionInputError(ValueError):
    """Raised when option/model inputs violate a documented precondition."""
