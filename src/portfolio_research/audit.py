"""Append-only, locally stored audit events with a verifiable hash chain."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from portfolio_research.config import PROJECT_ROOT, SmaSettings
from portfolio_research.market_data import validate_symbols

DEFAULT_AUDIT_PATH = PROJECT_ROOT / "data" / "audit.jsonl"
_EVENT_TYPE_PATTERN = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|password|secret|credential|authorization)", re.IGNORECASE
)
_MAX_EVENT_BYTES = 100_000
_MAX_BATCH_EVENTS = 200_000
_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_GENESIS_HASH = "0" * 64


class AuditLogError(RuntimeError):
    """Raised when an audit event cannot be safely validated or persisted."""


def _lock_for(path: Path) -> threading.Lock:
    normalized = path.resolve()
    with _LOCKS_GUARD:
        if normalized not in _LOCKS:
            _LOCKS[normalized] = threading.Lock()
        return _LOCKS[normalized]


def _validate_payload(value: Any, key_path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise AuditLogError(f"Audit object keys must be strings at {key_path}.")
            if _SECRET_KEY_PATTERN.search(key):
                raise AuditLogError(
                    f"Refusing to write secret-like audit field: {key_path}.{key}."
                )
            _validate_payload(item, f"{key_path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_payload(item, f"{key_path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise AuditLogError(f"Audit values must be finite at {key_path}.")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise AuditLogError(f"Unsupported audit value at {key_path}.")


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise AuditLogError(
            "Audit event could not be encoded as strict JSON."
        ) from error


def _event_hash(event: Mapping[str, Any]) -> str:
    unhashed = {key: value for key, value in event.items() if key != "event_hash"}
    return hashlib.sha256(_canonical_json(unhashed).encode("utf-8")).hexdigest()


def _verify_existing_log(path: Path) -> tuple[str, int]:
    previous_hash = _GENESIS_HASH
    event_count = 0
    if not path.exists():
        return previous_hash, event_count
    try:
        with path.open(encoding="utf-8") as audit_file:
            for line_number, line in enumerate(audit_file, start=1):
                if not line.strip():
                    raise AuditLogError(
                        f"Audit log contains an empty line at {line_number}."
                    )
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as error:
                    raise AuditLogError(
                        f"Audit log is invalid JSON at line {line_number}."
                    ) from error
                if (
                    not isinstance(event, dict)
                    or event.get("previous_hash") != previous_hash
                ):
                    raise AuditLogError(
                        f"Audit hash chain is invalid at line {line_number}."
                    )
                recorded_hash = event.get("event_hash")
                if not isinstance(recorded_hash, str) or recorded_hash != _event_hash(
                    event
                ):
                    raise AuditLogError(
                        f"Audit event hash is invalid at line {line_number}."
                    )
                previous_hash = recorded_hash
                event_count += 1
    except (OSError, UnicodeError) as error:
        raise AuditLogError(f"Audit log could not be read: {error}") from error
    return previous_hash, event_count


def append_audit_events(
    events: Sequence[tuple[str, Mapping[str, Any]]],
    log_path: Path = DEFAULT_AUDIT_PATH,
) -> tuple[str, ...]:
    """Validate and append a batch of hash-chained events in one file write."""
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        raise TypeError("Audit events must be a sequence of event/payload pairs.")
    if len(events) > _MAX_BATCH_EVENTS:
        raise AuditLogError("Audit batch exceeds the configured event-count limit.")
    if not events:
        return ()
    path = Path(log_path)
    lock = _lock_for(path)
    with lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            previous_hash, _ = _verify_existing_log(path)
            serialized_events: list[str] = []
            event_hashes: list[str] = []
            for event_type, payload in events:
                if not isinstance(event_type, str) or not _EVENT_TYPE_PATTERN.fullmatch(
                    event_type
                ):
                    raise AuditLogError("Audit event type has an invalid format.")
                if not isinstance(payload, Mapping):
                    raise AuditLogError("Audit event payload must be an object.")
                _validate_payload(payload)
                body = {
                    "created_at": datetime.now(UTC).isoformat(),
                    "event_type": event_type,
                    "payload": payload,
                    "previous_hash": previous_hash,
                }
                event_hash = _event_hash(body)
                serialized = _canonical_json({**body, "event_hash": event_hash})
                if len(serialized.encode("utf-8")) > _MAX_EVENT_BYTES:
                    raise AuditLogError("Audit event exceeds the size limit.")
                serialized_events.append(serialized)
                event_hashes.append(event_hash)
                previous_hash = event_hash
            with path.open("a", encoding="utf-8", newline="\n") as audit_file:
                audit_file.write("\n".join(serialized_events) + "\n")
                audit_file.flush()
                os.fsync(audit_file.fileno())
            return tuple(event_hashes)
        except AuditLogError:
            raise
        except OSError as error:
            raise AuditLogError(
                f"Audit events could not be written: {error}"
            ) from error


def append_audit_event(
    event_type: str,
    payload: Mapping[str, Any],
    log_path: Path = DEFAULT_AUDIT_PATH,
) -> str:
    """Append one validated event and return its integrity hash."""
    return append_audit_events([(event_type, payload)], log_path)[0]


def verify_audit_log(log_path: Path = DEFAULT_AUDIT_PATH) -> int:
    """Verify every event and return the valid event count."""
    path = Path(log_path)
    with _lock_for(path):
        _, event_count = _verify_existing_log(path)
        return event_count


def _series_value(series: pd.Series, index: pd.Index, label: str) -> float | None:
    if index not in series.index:
        return None
    value = series.loc[index]
    if pd.isna(value):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise AuditLogError(f"{label} must be finite.")
    return numeric_value


def audit_signal_run(
    strategy: str,
    symbols: Sequence[str],
    signals: pd.Series | pd.DataFrame,
    positions: pd.DataFrame,
    settings: SmaSettings,
    log_path: Path = DEFAULT_AUDIT_PATH,
) -> str:
    """Record every daily signal and its available position for one research run."""
    if not isinstance(strategy, str) or not strategy.strip():
        raise AuditLogError("Signal audit strategy must be non-empty text.")
    normalized_symbols = validate_symbols(symbols)
    if not isinstance(signals, (pd.Series, pd.DataFrame)):
        raise TypeError("Signals must be a pandas Series or DataFrame.")
    if not isinstance(positions, pd.DataFrame):
        raise TypeError("Positions must be a pandas DataFrame.")
    if not isinstance(signals.index, pd.DatetimeIndex) or not isinstance(
        positions.index, pd.DatetimeIndex
    ):
        raise AuditLogError("Signal and position dates must be timestamps.")
    if not signals.index.is_unique or not positions.index.is_unique:
        raise AuditLogError("Signal and position dates must be unique.")
    if not signals.index.is_monotonic_increasing:
        raise AuditLogError("Signal dates must be in chronological order.")
    if not positions.index.is_monotonic_increasing:
        raise AuditLogError("Position dates must be in chronological order.")
    if isinstance(signals, pd.Series):
        if len(normalized_symbols) != 1:
            raise AuditLogError("A signal series must identify exactly one ticker.")
    elif set(signals.columns) != set(normalized_symbols):
        raise AuditLogError("Signal columns must match the requested ticker symbols.")
    if set(positions.columns) != set(normalized_symbols):
        raise AuditLogError("Position columns must match the requested ticker symbols.")

    run_id = str(uuid.uuid4())
    events: list[tuple[str, Mapping[str, Any]]] = [
        (
            "research_run",
            {
                "run_id": run_id,
                "strategy": strategy.strip(),
                "symbols": list(normalized_symbols),
                "first_signal_date": signals.index[0].isoformat(),
                "last_signal_date": signals.index[-1].isoformat(),
                "transaction_cost_bps_per_side": (
                    settings.transaction_cost_bps_per_side
                ),
                "slippage_bps_per_side": settings.slippage_bps_per_side,
                "execution_delay_bars": settings.execution_delay_bars,
            },
        )
    ]
    for date_value in signals.index:
        if isinstance(signals, pd.Series):
            signal_payload: Any = _series_value(signals, date_value, "Signal")
        else:
            signal_payload = {
                symbol: _series_value(signals[symbol], date_value, "Target weight")
                for symbol in normalized_symbols
            }
        position_payload = {
            symbol: _series_value(positions[symbol], date_value, "Position")
            for symbol in normalized_symbols
        }
        events.append(
            (
                "strategy_signal",
                {
                    "run_id": run_id,
                    "date": date_value.isoformat(),
                    "signal": signal_payload,
                    "position": position_payload,
                },
            )
        )
    append_audit_events(events, log_path)
    return run_id
