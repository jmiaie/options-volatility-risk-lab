import pandas as pd
import pytest

from options_risk.chains import OptionChain


@pytest.fixture
def synthetic_chain() -> OptionChain:
    frame = pd.DataFrame(
        {
            "expiry_years": [0.25, 0.25, 0.5, 0.5],
            "strike": [95.0, 105.0, 95.2377978524705, 105.26282920483529],
            "option_type": ["call", "call", "call", "call"],
            "spot": [100.0, 100.0, 100.0, 100.0],
            "rate": [0.02, 0.02, 0.02, 0.02],
            "dividend_yield": [0.01, 0.01, 0.01, 0.01],
            "price": [7.2, 2.8, 8.5, 4.6],
            "implied_vol": [0.18, 0.21, 0.19, 0.22],
        }
    )
    return OptionChain.from_frame(frame)


def test_chain_validation_and_log_moneyness(synthetic_chain: OptionChain) -> None:
    enriched = synthetic_chain.with_log_moneyness()
    assert "log_moneyness" in enriched.columns
    assert enriched["log_moneyness"].iloc[0] < enriched["log_moneyness"].iloc[1]


def test_smile_and_term_structure_do_not_extrapolate(synthetic_chain: OptionChain) -> None:
    smile = synthetic_chain.smile(0.25)
    assert len(smile) == 2
    term = synthetic_chain.term_structure(smile["log_moneyness"].iloc[0])
    assert len(term) == 2
    with pytest.raises(ValueError, match="no extrapolation"):
        synthetic_chain.term_structure(0.5)
