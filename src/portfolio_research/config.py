"""Load and validate non-secret project configuration."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_CONFIG_PATH = PROJECT_ROOT / "config" / "project.yaml"
DEFAULT_STRATEGY_CONFIG_PATH = PROJECT_ROOT / "config" / "strategies.yaml"
DEFAULT_UNIVERSE_PATH = PROJECT_ROOT / "config" / "universe.yaml"


@dataclass(frozen=True)
class DataSettings:
    """Validated market-data settings loaded from the project YAML file."""

    provider: str
    cache_directory: Path
    cache_ttl_hours: float
    interval: str


@dataclass(frozen=True)
class SmaSettings:
    """Configured SMA windows, trading costs, and execution delay."""

    fast_window: int
    slow_window: int
    transaction_cost_bps_per_side: float
    slippage_bps_per_side: float
    execution_delay_bars: int


@dataclass(frozen=True)
class MetricSettings:
    """Configured annualisation, risk-free rate, and VaR confidence."""

    periods_per_year: int
    annual_risk_free_rate: float
    var_confidence: float


@dataclass(frozen=True)
class DashboardSettings:
    """Configured defaults for the interactive dashboard."""

    default_asset: str
    default_start_date: date
    default_end_date: date


@dataclass(frozen=True)
class Universe:
    """Configured stock sectors and ETF building blocks."""

    stocks_by_sector: Mapping[str, tuple[str, ...]]
    etfs: Mapping[str, str]

    @property
    def stock_symbols(self) -> tuple[str, ...]:
        """Return stock symbols in the order they appear in the config."""
        return tuple(
            symbol for symbols in self.stocks_by_sector.values() for symbol in symbols
        )

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return all stock and ETF symbols in configuration order."""
        return self.stock_symbols + tuple(self.etfs)


def load_data_settings(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> DataSettings:
    """Load the market-data configuration and reject unsupported settings."""
    try:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid project YAML configuration: {path}") from error

    if not isinstance(raw_config, dict) or not isinstance(raw_config.get("data"), dict):
        raise TypeError(f"Project config must contain a data mapping: {path}")
    data_config = raw_config["data"]
    provider = data_config.get("provider")
    interval = data_config.get("interval")
    cache_ttl_hours = data_config.get("cache_ttl_hours")
    cache_directory = data_config.get("cache_directory")

    if provider != "yfinance":
        raise ValueError(f"Unsupported market-data provider: {provider!r}")
    if interval != "1d":
        raise ValueError("Only daily ('1d') data is supported by this pipeline.")
    if (
        isinstance(cache_ttl_hours, bool)
        or not isinstance(cache_ttl_hours, (int, float))
        or not math.isfinite(cache_ttl_hours)
        or cache_ttl_hours < 0
    ):
        raise ValueError("data.cache_ttl_hours must be a non-negative number.")
    if not isinstance(cache_directory, str) or not cache_directory.strip():
        raise ValueError("data.cache_directory must be a non-empty path.")

    cache_path = Path(cache_directory)
    if not cache_path.is_absolute():
        cache_path = PROJECT_ROOT / cache_path
    return DataSettings(
        provider=provider,
        cache_directory=cache_path,
        cache_ttl_hours=float(cache_ttl_hours),
        interval=interval,
    )


def load_sma_settings(path: Path = DEFAULT_STRATEGY_CONFIG_PATH) -> SmaSettings:
    """Load SMA parameters and reject invalid or unsafe configurations."""
    try:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid strategy YAML configuration: {path}") from error

    sma = raw_config.get("sma") if isinstance(raw_config, dict) else None
    if not isinstance(sma, dict):
        raise TypeError(f"Strategy config must contain an sma mapping: {path}")

    fast_window = sma.get("fast_window")
    slow_window = sma.get("slow_window")
    transaction_cost = sma.get("transaction_cost_bps_per_side")
    slippage = sma.get("slippage_bps_per_side")
    execution_delay = sma.get("execution_delay_bars")
    if (
        isinstance(fast_window, bool)
        or not isinstance(fast_window, int)
        or fast_window <= 0
        or isinstance(slow_window, bool)
        or not isinstance(slow_window, int)
        or slow_window <= fast_window
    ):
        raise ValueError("SMA windows must be positive integers with fast < slow.")
    if (
        isinstance(execution_delay, bool)
        or not isinstance(execution_delay, int)
        or execution_delay < 1
    ):
        raise ValueError("execution_delay_bars must be an integer of at least 1.")
    costs = (transaction_cost, slippage)
    if any(
        isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not math.isfinite(cost)
        or cost < 0
        for cost in costs
    ):
        raise ValueError(
            "Configured cost and slippage must be finite and non-negative."
        )

    return SmaSettings(
        fast_window=fast_window,
        slow_window=slow_window,
        transaction_cost_bps_per_side=float(transaction_cost),
        slippage_bps_per_side=float(slippage),
        execution_delay_bars=execution_delay,
    )


def load_metric_settings(path: Path = DEFAULT_PROJECT_CONFIG_PATH) -> MetricSettings:
    """Load and validate performance-metric conventions."""
    try:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid project YAML configuration: {path}") from error

    analytics = raw_config.get("analytics") if isinstance(raw_config, dict) else None
    if not isinstance(analytics, dict):
        raise TypeError(f"Project config must contain an analytics mapping: {path}")
    periods_per_year = analytics.get("periods_per_year")
    annual_risk_free_rate = analytics.get("annual_risk_free_rate")
    var_confidence = analytics.get("var_confidence")
    if (
        isinstance(periods_per_year, bool)
        or not isinstance(periods_per_year, int)
        or periods_per_year <= 0
    ):
        raise ValueError("analytics.periods_per_year must be a positive integer.")
    if (
        isinstance(annual_risk_free_rate, bool)
        or not isinstance(annual_risk_free_rate, (int, float))
        or not math.isfinite(annual_risk_free_rate)
        or annual_risk_free_rate <= -1
    ):
        raise ValueError("analytics.annual_risk_free_rate must be finite and > -1.")
    if (
        isinstance(var_confidence, bool)
        or not isinstance(var_confidence, (int, float))
        or not 0 < var_confidence < 1
    ):
        raise ValueError("analytics.var_confidence must be between 0 and 1.")

    return MetricSettings(
        periods_per_year=periods_per_year,
        annual_risk_free_rate=float(annual_risk_free_rate),
        var_confidence=float(var_confidence),
    )


def load_dashboard_settings(
    path: Path = DEFAULT_PROJECT_CONFIG_PATH,
) -> DashboardSettings:
    """Load and validate dashboard defaults from the project YAML."""
    try:
        with path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid project YAML configuration: {path}") from error

    dashboard = raw_config.get("dashboard") if isinstance(raw_config, dict) else None
    if not isinstance(dashboard, dict):
        raise TypeError(f"Project config must contain a dashboard mapping: {path}")
    asset = dashboard.get("default_asset")
    start_date = dashboard.get("default_start_date")
    end_date = dashboard.get("default_end_date")
    if not isinstance(asset, str) or not asset.strip():
        raise ValueError("dashboard.default_asset must be a non-empty symbol.")

    def parse_config_date(value: object, name: str) -> date:
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as error:
                raise ValueError(f"dashboard.{name} must be an ISO date.") from error
        raise TypeError(f"dashboard.{name} must be an ISO date.")

    parsed_start = parse_config_date(start_date, "default_start_date")
    parsed_end = parse_config_date(end_date, "default_end_date")
    if parsed_start >= parsed_end:
        raise ValueError("Dashboard default start date must be before its end date.")
    return DashboardSettings(
        default_asset=asset.strip().upper(),
        default_start_date=parsed_start,
        default_end_date=parsed_end,
    )


def load_universe(path: Path = DEFAULT_UNIVERSE_PATH) -> Universe:
    """Load the fixed asset universe and reject malformed configuration."""
    with path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file)

    if not isinstance(raw_config, dict):
        raise TypeError(f"Universe config must be a mapping: {path}")

    stock_config = raw_config.get("stocks_by_sector")
    etf_config = raw_config.get("etfs")
    if not isinstance(stock_config, dict) or not isinstance(etf_config, dict):
        raise TypeError("Universe config requires stocks_by_sector and etfs mappings.")

    stocks_by_sector: dict[str, tuple[str, ...]] = {}
    for sector, raw_symbols in stock_config.items():
        if not isinstance(sector, str) or not sector.strip():
            raise ValueError("Every stock sector must have a non-empty name.")
        if (
            not isinstance(raw_symbols, list)
            or not raw_symbols
            or any(
                not isinstance(symbol, str) or not symbol.strip()
                for symbol in raw_symbols
            )
        ):
            raise ValueError(f"Sector {sector!r} must contain stock symbols.")
        stocks_by_sector[sector] = tuple(
            symbol.strip().upper() for symbol in raw_symbols
        )

    if any(
        not isinstance(symbol, str)
        or not symbol.strip()
        or not isinstance(description, str)
        or not description.strip()
        for symbol, description in etf_config.items()
    ):
        raise ValueError("Every ETF must have a symbol and description.")

    etfs = {
        symbol.strip().upper(): description.strip()
        for symbol, description in etf_config.items()
    }
    all_symbols = [
        *(
            symbol
            for sector_symbols in stocks_by_sector.values()
            for symbol in sector_symbols
        ),
        *etfs,
    ]
    if len(all_symbols) != len(set(all_symbols)):
        raise ValueError("A symbol may appear only once in the universe.")

    return Universe(stocks_by_sector=stocks_by_sector, etfs=etfs)
