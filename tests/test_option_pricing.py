import math

import pytest

from quant_models.options import binomial_tree_price, black_scholes_price


def test_black_scholes_matches_standard_atm_european_prices() -> None:
    call = black_scholes_price(100, 100, 1, 0.05, 0.2, "call")
    put = black_scholes_price(100, 100, 1, 0.05, 0.2, "put")

    assert call == pytest.approx(10.450583572185565, abs=1e-10)
    assert put == pytest.approx(5.573526022256971, abs=1e-10)


def test_black_scholes_put_call_parity_includes_dividend_yield() -> None:
    spot, strike, time, rate, dividend, volatility = 100, 105, 0.75, 0.04, 0.015, 0.3
    call = black_scholes_price(spot, strike, time, rate, volatility, "call", dividend)
    put = black_scholes_price(spot, strike, time, rate, volatility, "put", dividend)

    assert call - put == pytest.approx(
        spot * math.exp(-dividend * time) - strike * math.exp(-rate * time),
        abs=1e-10,
    )


def test_binomial_european_converges_toward_black_scholes() -> None:
    analytic = black_scholes_price(100, 100, 1, 0.05, 0.2, "call")
    tree = binomial_tree_price(100, 100, 1, 0.05, 0.2, "call", steps=1000)

    assert tree == pytest.approx(analytic, abs=0.02)


def test_american_put_is_not_cheaper_than_european_put() -> None:
    european = binomial_tree_price(
        45, 50, 1, 0.1, 0.2, "put", steps=500, exercise_style="european"
    )
    american = binomial_tree_price(
        45, 50, 1, 0.1, 0.2, "put", steps=500, exercise_style="american"
    )

    assert american >= european


def test_zero_volatility_uses_discounted_deterministic_payoff() -> None:
    call = black_scholes_price(100, 100, 1, 0.05, 0, "call")
    put = black_scholes_price(100, 100, 1, 0.05, 0, "put")

    assert call == pytest.approx(100 - 100 * math.exp(-0.05))
    assert put == 0


def test_expired_option_returns_intrinsic_value() -> None:
    assert black_scholes_price(105, 100, 0, 0.05, 0.2, "call") == 5
    assert binomial_tree_price(95, 100, 0, 0.05, 0.2, "put") == 5


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"spot": 0}, "spot and strike must be positive"),
        ({"time_to_expiry_years": -1}, "must not be negative"),
        ({"volatility": -0.1}, "volatility must not be negative"),
        ({"risk_free_rate": math.inf}, "risk_free_rate must be a finite number"),
        ({"option_type": "binary"}, "option_type must be 'call' or 'put'"),
    ],
)
def test_black_scholes_rejects_invalid_inputs(kwargs, message) -> None:
    inputs = {
        "spot": 100,
        "strike": 100,
        "time_to_expiry_years": 1,
        "risk_free_rate": 0.05,
        "volatility": 0.2,
        "option_type": "call",
    }
    inputs.update(kwargs)

    with pytest.raises(ValueError, match=message):
        black_scholes_price(**inputs)


@pytest.mark.parametrize("steps", [0, -1, True, 2_001, 1.5])
def test_binomial_tree_rejects_invalid_step_counts(steps) -> None:
    with pytest.raises(ValueError, match="steps"):
        binomial_tree_price(100, 100, 1, 0.05, 0.2, "call", steps=steps)


def test_binomial_tree_rejects_risk_neutral_probability_outside_bounds() -> None:
    with pytest.raises(ValueError, match="no-arbitrage bounds"):
        binomial_tree_price(
            100, 100, 1, 0.0, 0.001, "call", steps=1, dividend_yield=1.0
        )
