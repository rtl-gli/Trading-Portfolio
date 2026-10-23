"""Load and validate non-secret project configuration."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_CONFIG_PATH = PROJECT_ROOT / "config" / "project.yaml"
DEFAULT_UNIVERSE_PATH = PROJECT_ROOT / "config" / "universe.yaml"


@dataclass(frozen=True)
class DataSettings:
    """Validated market-data settings loaded from the project YAML file."""

    provider: str
    cache_directory: Path
    cache_ttl_hours: float
    interval: str


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
