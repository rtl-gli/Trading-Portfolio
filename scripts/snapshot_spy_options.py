"""Create a validated local SPY option-chain snapshot using yfinance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yfinance as yf

from quant_models.data.options_snapshot import (
    DEFAULT_OPTIONS_CONFIG,
    OptionSnapshotError,
    capture_option_snapshot,
    load_snapshot_settings,
)


def main() -> int:
    """Run one snapshot and print a concise result for local or scheduled use."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_OPTIONS_CONFIG,
        help="Path to the non-secret options YAML configuration.",
    )
    arguments = parser.parse_args()
    try:
        settings = load_snapshot_settings(arguments.config)
        result = capture_option_snapshot(
            yf.Ticker(settings.underlying),
            settings,
        )
    except (OptionSnapshotError, OSError, ValueError) as error:
        parser.exit(1, f"Snapshot failed: {error}\n")
    print(
        json.dumps(
            {
                "snapshot_date": result.snapshot_date.isoformat(),
                "contract_count": result.contract_count,
                "expiration_count": result.expiration_count,
                "manifest": str(result.manifest_path),
                "data": str(result.data_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
