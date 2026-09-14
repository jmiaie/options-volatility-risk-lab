from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "expiry_years",
    "strike",
    "option_type",
    "spot",
    "rate",
    "dividend_yield",
}
VALID_OPTION_TYPES = {"call", "put"}


@dataclass(frozen=True)
class OptionChain:
    quotes: pd.DataFrame

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> OptionChain:
        missing = REQUIRED_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        if "price" not in frame.columns and "implied_vol" not in frame.columns:
            raise ValueError("Option chain requires at least one of 'price' or 'implied_vol'")
        quotes = frame.copy()
        if not quotes["option_type"].isin(VALID_OPTION_TYPES).all():
            raise ValueError("option_type must contain only 'call' or 'put'")
        for column in ["expiry_years", "strike", "spot"]:
            if (quotes[column] <= 0.0).any():
                raise ValueError(f"{column} must be strictly positive")
        for column in ["rate", "dividend_yield"]:
            if not np.isfinite(quotes[column]).all():
                raise ValueError(f"{column} must be finite")
        if (
            "price" in quotes.columns
            and ((quotes["price"] < 0.0) | (~np.isfinite(quotes["price"]))).any()
        ):
            raise ValueError("price must be finite and non-negative")
        if "implied_vol" in quotes.columns:
            valid_iv = quotes["implied_vol"].isna() | (
                (quotes["implied_vol"] >= 0.0) & np.isfinite(quotes["implied_vol"])
            )
            if not valid_iv.all():
                raise ValueError("implied_vol must be finite, non-negative, or missing")
        return cls(quotes.reset_index(drop=True))

    def with_log_moneyness(self) -> pd.DataFrame:
        frame = self.quotes.copy()
        forward = frame["spot"] * np.exp(
            (frame["rate"] - frame["dividend_yield"]) * frame["expiry_years"]
        )
        frame["log_moneyness"] = np.log(frame["strike"] / forward)
        return frame

    def smile(self, expiry_years: float, *, tolerance: float = 1e-8) -> pd.DataFrame:
        frame = self.with_log_moneyness()
        mask = np.isclose(frame["expiry_years"], expiry_years, atol=tolerance, rtol=0.0)
        if not mask.any():
            raise ValueError("No smile slice found for the requested expiry_years")
        return frame.loc[mask].sort_values(["log_moneyness", "strike"]).reset_index(drop=True)

    def term_structure(self, log_moneyness: float, *, tolerance: float = 1e-6) -> pd.DataFrame:
        frame = self.with_log_moneyness()
        mask = np.abs(frame["log_moneyness"] - log_moneyness) <= tolerance
        if not mask.any():
            raise ValueError(
                "No quotes found at the requested log-moneyness within "
                "tolerance; no extrapolation performed"
            )
        return frame.loc[mask].sort_values(["expiry_years", "strike"]).reset_index(drop=True)

    def volatility_surface(self) -> pd.DataFrame:
        if "implied_vol" not in self.quotes.columns:
            raise ValueError("volatility_surface requires an 'implied_vol' column")
        duplicated = self.quotes.duplicated(subset=["expiry_years", "strike", "option_type"])
        if duplicated.any():
            raise ValueError(
                "Surface construction requires unique (expiry_years, strike, option_type) rows"
            )
        return self.with_log_moneyness().pivot(
            index="expiry_years", columns="strike", values="implied_vol"
        )
