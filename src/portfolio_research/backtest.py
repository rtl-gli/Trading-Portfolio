"""Cost-aware, long-only SMA and buy-and-hold backtests."""

from dataclasses import dataclass

import pandas as pd

from portfolio_research.config import SmaSettings, load_sma_settings
from portfolio_research.market_data import validate_prices


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
    fast_average = validated_prices.rolling(
        window=selected_settings.fast_window,
        min_periods=selected_settings.fast_window,
    ).mean()
    slow_average = validated_prices.rolling(
        window=selected_settings.slow_window,
        min_periods=selected_settings.slow_window,
    ).mean()
    signal_is_available = fast_average.notna() & slow_average.notna()
    signals = fast_average.gt(slow_average).where(signal_is_available).astype(float)
    positions = signals.shift(selected_settings.execution_delay_bars + 1).fillna(0.0)
    turnover = signals.fillna(0.0).diff().abs().fillna(0.0)
    turnover = turnover.shift(selected_settings.execution_delay_bars).fillna(0.0)
    terminal_position = signals.shift(selected_settings.execution_delay_bars).fillna(
        0.0
    )
    turnover.iloc[-1] += abs(terminal_position.iloc[-1])

    asset_returns = validated_prices.pct_change(fill_method=None)
    asset_returns.iloc[0] = 0.0
    sma_result = _result_from_positions(
        asset_returns, signals, positions, turnover, selected_settings
    )

    benchmark_positions = pd.Series(1.0, index=validated_prices.index, name="position")
    benchmark_turnover = pd.Series(0.0, index=validated_prices.index)
    benchmark_turnover.iloc[0] = 1.0
    benchmark_turnover.iloc[-1] += 1.0
    benchmark_signals = benchmark_positions.rename("signal")
    benchmark_result = _result_from_positions(
        asset_returns,
        benchmark_signals,
        benchmark_positions,
        benchmark_turnover,
        selected_settings,
    )
    return BacktestComparison(sma=sma_result, buy_and_hold=benchmark_result)
