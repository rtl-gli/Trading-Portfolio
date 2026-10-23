import json

import numpy as np
import pandas as pd
import pytest

from portfolio_research.audit import (
    AuditLogError,
    append_audit_event,
    audit_signal_run,
    verify_audit_log,
)
from portfolio_research.config import SmaSettings


def test_signal_audit_records_every_date_and_verifies_hash_chain(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    index = pd.bdate_range("2024-01-01", periods=4)
    signals = pd.Series([np.nan, 0.0, 1.0, 1.0], index=index)
    positions = pd.DataFrame({"SPY": [0.0, 0.0, 1.0, 1.0]}, index=index)

    run_id = audit_signal_run(
        "SMA crossover",
        ["spy"],
        signals,
        positions,
        SmaSettings(2, 3, 5, 5, 1),
        path,
    )

    entries = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert verify_audit_log(path) == 5
    assert entries[0]["event_type"] == "research_run"
    assert entries[1]["payload"]["signal"] is None
    assert all(entry["payload"]["run_id"] == run_id for entry in entries)


def test_audit_refuses_secret_like_fields_and_nonfinite_values(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"

    with pytest.raises(AuditLogError, match="secret-like"):
        append_audit_event("test_event", {"api_key": "must-not-be-written"}, path)
    with pytest.raises(AuditLogError, match="finite"):
        append_audit_event("test_event", {"value": float("nan")}, path)
    assert not path.exists()


def test_audit_verification_detects_tampered_events(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    append_audit_event("test_event", {"value": 1}, path)
    append_audit_event("test_event", {"value": 2}, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["payload"]["value"] = 9
    lines[0] = json.dumps(event)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(AuditLogError, match="invalid at line 1"):
        verify_audit_log(path)
