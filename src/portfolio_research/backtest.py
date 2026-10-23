"""Cost-aware, long-only SMA and buy-and-hold backtests."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from portfolio_research.config import SmaSettings, load_sma_settings
from portfolio_research.market_data import validate_prices
from portfolio_research.strategies import sma_signals


@dataclass(frozen=True)
class PortfolioBacktestResult:
    """Daily multi-asset weights, portfolio returns, and trading costs."""

    positions: pd.DataFrame
    gross_returns: pd.Series
    transaction_costs: pd.Series
    net_returns: pd.Series


@dataclass(frozen=True)
class BacktestResult:
    """Daily strategy signals, positions, returns, and trading costs."""

    signals: pd.Series
    positions: pd.Series
    gross_returns: pd.Series
    transaction_costs: pd.Series
    net_returns: pd.Series


@dataclass(frozen=True)
class BacktestComparison:
    """Matched SMA and buy-and-hold results for one asset."""

    sma: BacktestResult
    buy_and_hold: BacktestResult


def _prepare_prices(prices: pd.Series, minimum_rows: int) -> pd.Series:
    if not isinstance(prices, pd.Series):
        raise TypeError("Backtest prices must be a pandas Series.")
    if prices.isna().any():
        missing_dates = prices.index[prices.isna()].tolist()
        raise ValueError(
            f"Backtest input contains missing prices on {missing_dates[:5]}."
        )
    panel, _ = validate_prices(prices.rename("ASSET").to_frame(), ["ASSET"])
    validated = panel["ASSET"]
    if len(validated) < minimum_rows:
        raise ValueError(
            f"Need at least {minimum_rows} daily prices for configured SMA windows "
            "and execution delay."
        )
    return validated


def _result_from_positions(
    asset_returns: pd.Series,
    signals: pd.Series,
    positions: pd.Series,
    turnover: pd.Series,
    settings: SmaSettings,
) -> BacktestResult:
    cost_per_turnover = (
        settings.transaction_cost_bps_per_side + settings.slippage_bps_per_side
    ) / 10_000
    gross_returns = asset_returns * positions
    transaction_costs = turnover * cost_per_turnover
    net_returns = (1 + gross_returns) * (1 - transaction_costs) - 1
    return BacktestResult(
        signals=signals,
        positions=positions,
        gross_returns=gross_returns,
        transaction_costs=transaction_costs,
        net_returns=net_returns,
    )


def run_signal_backtest(
    prices: pd.Series,
    signals: pd.Series,
    settings: SmaSettings | None = None,
) -> BacktestResult:
    """Backtest long-only zero/one target signals with delayed fills and costs."""
    selected_settings = settings or load_sma_settings()
    validated_prices = _prepare_prices(prices, 2)
    if not isinstance(signals, pd.Series):
        raise TypeError("Strategy signals must be a pandas Series.")
    if not signals.index.equals(validated_prices.index):
        raise ValueError("Signal dates must exactly match the validated price dates.")
    available_signals = signals.dropna()
    if not available_signals.isin([0.0, 1.0]).all():
        raise ValueError("Long-only signals must be zero or one.")

    positions = signals.shift(selected_settings.execution_delay_bars + 1).fillna(0.0)
    turnover = positions.diff().abs().fillna(0.0)
    turnover.iloc[-1] += abs(positions.iloc[-1])
    asset_returns = validated_prices.pct_change(fill_method=None)
    asset_returns.iloc[0] = 0.0
    return _result_from_positions(
        asset_returns, signals, positions, turnover, selected_settings
    )


def run_portfolio_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    settings: SmaSettings | None = None,
) -> PortfolioBacktestResult:
    """Backtest long-only portfolio weights with delayed execution and costs.

    The full L1 change in portfolio weights is turnover, so buys and sells both
    pay the configured per-side cost. The final holdings are liquidated.
    """
    selected_settings = settings or load_sma_settings()
    validated_prices, _ = validate_prices(prices)
    if validated_prices.isna().any().any():
        raise ValueError("Portfolio backtest prices contain missing observations.")
    if not target_weights.index.equals(validated_prices.index):
        raise ValueError("Target weight dates must match the price dates exactly.")
    if set(target_weights.columns) != set(validated_prices.columns):
        raise ValueError("Target weight columns must match the price columns exactly.")
    targets = target_weights.loc[:, validated_prices.columns].copy()
    available = targets.notna().all(axis=1)
    if targets.notna().any(axis=1).ne(available).any():
        raise ValueError(
            "Each target weight row must be either fully set or fully empty."
        )
    if available.any():
        available_targets = targets.loc[available]
        values = available_targets.to_numpy()
        if not np.isfinite(values).all():
            raise ValueError("Target weights must be finite.")
        if (values < 0).any():
            raise ValueError("Portfolio weights must be long-only.")
        if (values > 1).any() or not np.allclose(values.sum(axis=1), 1.0):
            raise ValueError(
                "Available portfolio weights must sum to 1 and not exceed 1."
            )
    if not available.any():
        raise ValueError("At least one portfolio target weight row is required.")

    execution_delay = selected_settings.execution_delay_bars + 1
    target_events = available.shift(execution_delay, fill_value=False)
    scheduled_targets = targets.ffill().shift(execution_delay).fillna(0.0)
    positions = pd.DataFrame(0.0, index=validated_prices.index, columns=targets.columns)
    asset_returns = validated_prices.pct_change(fill_method=None)
    asset_returns.iloc[0] = 0.0
    gross_returns = pd.Series(0.0, index=validated_prices.index, name="gross_return")
    turnover = pd.Series(0.0, index=validated_prices.index, name="turnover")
    drifted_holdings = np.zeros(len(validated_prices.columns))
    for row_number, row_date in enumerate(validated_prices.index):
        daily_returns = asset_returns.loc[row_date].to_numpy(dtype=float)
        if target_events.iloc[row_number]:
            holdings = scheduled_targets.loc[row_date].to_numpy(dtype=float)
            turnover.loc[row_date] = np.abs(holdings - drifted_holdings).sum()
        else:
            holdings = drifted_holdings.copy()
        positions.loc[row_date] = holdings
        portfolio_return = float(holdings @ daily_returns)
        gross_returns.loc[row_date] = portfolio_return
        end_of_day_value = holdings * (1 + daily_returns)
        drifted_holdings = end_of_day_value / (1 + portfolio_return)
    turnover.iloc[-1] += float(np.abs(drifted_holdings).sum())
    cost_per_turnover = (
        selected_settings.transaction_cost_bps_per_side
        + selected_settings.slippage_bps_per_side
    ) / 10_000
    costs = turnover * cost_per_turnover
    net_returns = (1 + gross_returns) * (1 - costs) - 1
    return PortfolioBacktestResult(
        positions=positions,
        gross_returns=gross_returns,
        transaction_costs=costs,
        net_returns=net_returns,
    )


def run_buy_and_hold_backtest(
    prices: pd.Series, settings: SmaSettings | None = None
) -> BacktestResult:
    """Buy an asset at the start, charge costs, and liquidate at the end."""
    selected_settings = settings or load_sma_settings()
    validated_prices = _prepare_prices(prices, 2)
    positions = pd.Series(1.0, index=validated_prices.index, name="position")
    signals = positions.rename("signal")
    turnover = pd.Series(0.0, index=validated_prices.index)
    turnover.iloc[0] = 1.0
    turnover.iloc[-1] += 1.0
    asset_returns = validated_prices.pct_change(fill_method=None)
    asset_returns.iloc[0] = 0.0
    return _result_from_positions(
        asset_returns, signals, positions, turnover, selected_settings
    )


def run_sma_vs_buy_and_hold(
    prices: pd.Series, settings: SmaSettings | None = None
) -> BacktestComparison:
    """Compare an SMA crossover with buy-and-hold using adjusted daily closes.

    A signal formed at a close is filled at a later close. Positions are
    delayed by one additional return bar so the strategy cannot earn a return
    from before its assumed fill. Costs are charged on each trade and on final
    liquidation; the buy-and-hold benchmark also pays entry costs.
    """
    selected_settings = settings or load_sma_settings()
    minimum_rows = (
        selected_settings.slow_window + selected_settings.execution_delay_bars + 1
    )
    validated_prices = _prepare_prices(prices, minimum_rows)
    signals = sma_signals(
        validated_prices,
        selected_settings.fast_window,
        selected_settings.slow_window,
    )
    sma_result = run_signal_backtest(validated_prices, signals, selected_settings)

    benchmark_result = run_buy_and_hold_backtest(validated_prices, selected_settings)
    return BacktestComparison(sma=sma_result, buy_and_hold=benchmark_result)
