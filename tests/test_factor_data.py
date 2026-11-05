from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd
import pytest

from quant_models.factors import data
from quant_models.factors.data import (
    FactorDataError,
    load_fama_french_factors,
    parse_fama_french_monthly_csv,
)

FF3_CSV = (
    "This file contains monthly factors\n"
    ",Mkt-RF,SMB,HML,RF\n"
    "201301,1.00,-2.00,0.50,0.10\n"
    "201302,-99.99,0.00,0.00,0.00\n"
    "Annual Factors: January-December\n"
    "2013,1.0,2.0,3.0,0.1\n"
)

FF5_CSV = "Header\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n201301,1.00,2.00,3.00,4.00,5.00,0.10\n"


def _archive(filename: str, csv_content: str) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(filename, csv_content)
    return buffer.getvalue()


def test_parse_ff3_monthly_csv_converts_percent_and_marks_sentinels() -> None:
    factors = parse_fama_french_monthly_csv(FF3_CSV, "ff3")

    assert factors.index.equals(
        pd.DatetimeIndex(["2013-01-31", "2013-02-28"], name="date")
    )
    assert factors.loc["2013-01-31", "Mkt-RF"] == pytest.approx(0.01)
    assert factors.loc["2013-01-31", "RF"] == pytest.approx(0.001)
    assert np.isnan(factors.loc["2013-02-28", "Mkt-RF"])


def test_parse_ff5_monthly_csv_includes_profitability_and_investment() -> None:
    factors = parse_fama_french_monthly_csv(FF5_CSV, "ff5")

    assert list(factors.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert factors.loc["2013-01-31", "RMW"] == pytest.approx(0.04)
    assert factors.loc["2013-01-31", "CMA"] == pytest.approx(0.05)


def test_factor_loader_downloads_once_then_verifies_local_cache(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _archive("F-F_Research_Data_Factors.CSV", FF3_CSV)
    calls = []

    def fake_download(url: str, timeout_seconds: float) -> bytes:
        calls.append((url, timeout_seconds))
        return archive

    monkeypatch.setattr(data, "_download_archive", fake_download)
    first = load_fama_french_factors("ff3", tmp_path)
    second = load_fama_french_factors("ff3", tmp_path, offline=True)

    assert first.source == "ken_french"
    assert second.source == "cache"
    assert first.sha256 == second.sha256
    assert second.factors.equals(first.factors)
    assert len(calls) == 1


def test_factor_loader_rejects_modified_cached_archive(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = _archive("F-F_Research_Data_Factors.CSV", FF3_CSV)
    monkeypatch.setattr(data, "_download_archive", lambda url, timeout: archive)
    load_fama_french_factors("ff3", tmp_path)
    cached_archive = tmp_path / "ken_french_ff3_monthly.zip"
    cached_archive.write_bytes(cached_archive.read_bytes() + b"changed")

    with pytest.raises(FactorDataError, match="SHA-256"):
        load_fama_french_factors("ff3", tmp_path)


def test_factor_loader_rejects_wrong_csv_in_archive(tmp_path, monkeypatch) -> None:
    archive = _archive("unexpected.csv", FF3_CSV)
    monkeypatch.setattr(data, "_download_archive", lambda url, timeout: archive)

    with pytest.raises(FactorDataError, match="must contain one"):
        load_fama_french_factors("ff3", tmp_path)


def test_factor_parser_rejects_annual_only_or_invalid_data() -> None:
    with pytest.raises(FactorDataError, match="no monthly rows"):
        parse_fama_french_monthly_csv(
            ",Mkt-RF,SMB,HML,RF\nAnnual Factors: January-December\n",
            "ff3",
        )
    with pytest.raises(FactorDataError, match="not numeric"):
        parse_fama_french_monthly_csv(
            ",Mkt-RF,SMB,HML,RF\n201301,invalid,0,0,0\n",
            "ff3",
        )
