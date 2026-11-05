"""European Black-Scholes and Cox-Ross-Rubinstein option pricing."""

from __future__ import annotations

from math import erf, exp, isfinite, log, sqrt
from numbers import Real
from typing import Literal

import numpy as np

OptionType = Literal["call", "put"]
ExerciseStyle = Literal["european", "american"]
MAX_TREE_STEPS = 2_000


def _validate_contract(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    volatility: float,
    dividend_yield: float,
    option_type: str,
) -> None:
    values = {
        "spot": spot,
        "strike": strike,
        "time_to_expiry_years": time_to_expiry_years,
        "risk_free_rate": risk_free_rate,
        "volatility": volatility,
        "dividend_yield": dividend_yield,
    }
    for name, value in values.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not isfinite(value)
        ):
            raise ValueError(f"{name} must be a finite number.")
    if spot <= 0 or strike <= 0:
        raise ValueError("spot and strike must be positive.")
    if time_to_expiry_years < 0:
        raise ValueError("time_to_expiry_years must not be negative.")
    if volatility < 0:
        raise ValueError("volatility must not be negative.")
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'.")


def _payoff(stock_price: float | np.ndarray, strike: float, option_type: str):
    if option_type == "call":
        return np.maximum(stock_price - strike, 0.0)
    return np.maximum(strike - stock_price, 0.0)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
) -> float:
    """Price a European option with continuous rates and dividend yield.

    Volatility and rates are annualized decimals. The function supports the
    deterministic zero-volatility boundary and immediate expiry.
    """
    _validate_contract(
        spot,
        strike,
        time_to_expiry_years,
        risk_free_rate,
        volatility,
        dividend_yield,
        option_type,
    )
    if time_to_expiry_years == 0:
        return float(_payoff(spot, strike, option_type))

    discounted_spot = spot * exp(-dividend_yield * time_to_expiry_years)
    discounted_strike = strike * exp(-risk_free_rate * time_to_expiry_years)
    if volatility == 0:
        if option_type == "call":
            return max(discounted_spot - discounted_strike, 0.0)
        return max(discounted_strike - discounted_spot, 0.0)

    sigma_root_time = volatility * sqrt(time_to_expiry_years)
    d1 = (
        log(spot / strike)
        + (risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry_years
    ) / sigma_root_time
    d2 = d1 - sigma_root_time

    if option_type == "call":
        price = discounted_spot * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
    else:
        price = discounted_strike * _normal_cdf(-d2) - discounted_spot * _normal_cdf(
            -d1
        )
    return max(price, 0.0)


def binomial_tree_price(
    spot: float,
    strike: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    steps: int = 500,
    dividend_yield: float = 0.0,
    exercise_style: ExerciseStyle = "european",
) -> float:
    """Price an option with a recombining Cox-Ross-Rubinstein tree.

    American exercise is checked at each node. A no-arbitrage risk-neutral
    probability outside [0, 1] is rejected instead of silently clipped.
    """
    _validate_contract(
        spot,
        strike,
        time_to_expiry_years,
        risk_free_rate,
        volatility,
        dividend_yield,
        option_type,
    )
    if exercise_style not in ("european", "american"):
        raise ValueError("exercise_style must be 'european' or 'american'.")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer.")
    if steps > MAX_TREE_STEPS:
        raise ValueError(f"steps must not exceed {MAX_TREE_STEPS}.")
    if time_to_expiry_years == 0:
        return float(_payoff(spot, strike, option_type))

    time_step = time_to_expiry_years / steps
    try:
        up = exp(volatility * sqrt(time_step))
        down = 1.0 / up
        growth = exp((risk_free_rate - dividend_yield) * time_step)
        discount = exp(-risk_free_rate * time_step)
    except OverflowError as error:
        raise ValueError(
            "Inputs cause numerical overflow in the binomial tree."
        ) from error

    if volatility == 0 or up == down:
        if exercise_style == "european":
            return black_scholes_price(
                spot,
                strike,
                time_to_expiry_years,
                risk_free_rate,
                volatility,
                option_type,
                dividend_yield,
            )
        exercise_values = []
        for step in range(steps + 1):
            elapsed = time_step * step
            deterministic_spot = spot * exp((risk_free_rate - dividend_yield) * elapsed)
            exercise_values.append(
                exp(-risk_free_rate * elapsed)
                * float(_payoff(deterministic_spot, strike, option_type))
            )
        return max(exercise_values)

    probability_up = (growth - down) / (up - down)
    if not 0.0 <= probability_up <= 1.0:
        raise ValueError(
            "Inputs violate the binomial tree's risk-neutral no-arbitrage bounds."
        )

    up_moves = np.arange(steps + 1, dtype=float)
    terminal_prices = spot * np.exp(up_moves * log(up) + (steps - up_moves) * log(down))
    values = _payoff(terminal_prices, strike, option_type)

    for step in range(steps - 1, -1, -1):
        values = discount * (
            probability_up * values[1:] + (1.0 - probability_up) * values[:-1]
        )
        if exercise_style == "american":
            up_moves = np.arange(step + 1, dtype=float)
            node_prices = spot * np.exp(
                up_moves * log(up) + (step - up_moves) * log(down)
            )
            values = np.maximum(values, _payoff(node_prices, strike, option_type))

    return float(values[0])
