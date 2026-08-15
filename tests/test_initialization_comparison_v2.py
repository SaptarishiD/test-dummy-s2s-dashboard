from __future__ import annotations

import numpy as np
import pytest
import json
import xarray as xr
from pathlib import Path

import scripts.build_initialization_comparison as comparison
from scripts.build_initialization_comparison import (
    pair_metrics,
    validate_matched,
    weighted_pattern_correlation,
)


def source(offset: float = 0.0, members: int = 100) -> dict:
    base = np.arange(24, dtype=float).reshape(6, 2, 2) + offset
    return {
        "members": members,
        "latitude": np.array([1.5, 0.0]),
        "longitude": np.array([60.0, 61.5]),
        "valid_start": np.arange(6).astype("timedelta64[D]") + np.datetime64("2026-08-15"),
        "valid_end": np.arange(6).astype("timedelta64[D]") + np.datetime64("2026-08-21"),
        "rain_mean": base,
        "temperature_mean": base,
        "rain_spread": np.ones_like(base),
        "temperature_spread": np.ones_like(base) * 2,
    }


def test_three_sources_must_match_members_and_coordinates() -> None:
    fields = {"gfs": source(), "era5": source(1), "ifs": source(2)}
    validate_matched(fields)
    fields["ifs"]["members"] = 5
    with pytest.raises(ValueError, match="ensemble sizes"):
        validate_matched(fields)


def test_pair_metrics_include_difference_map_and_spread() -> None:
    metrics = pair_metrics(source(2), source(), "rain", 0, np.ones((2, 2)))
    assert metrics["difference_field"] == [2.0, 2.0, 2.0, 2.0]
    assert metrics["area_weighted_mean_difference"] == 2.0
    assert metrics["mean_absolute_difference"] == 2.0
    assert metrics["ensemble_mean_pattern_correlation"] == 1.0
    assert metrics["left_mean_spread"] == metrics["right_mean_spread"] == 1.0


def test_constant_pattern_correlation_is_defined_as_zero() -> None:
    values = np.ones((2, 2))
    assert weighted_pattern_correlation(values, values, np.ones_like(values)) == 0.0


def test_builder_publishes_all_three_pairs(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    monkeypatch.setattr(comparison, "DATA", data)
    monkeypatch.setattr(comparison, "PUBLIC", tmp_path)
    monkeypatch.setattr(comparison, "build_catalog", lambda existing, *_: existing)
    date = "20260815"
    paths = {}
    starts = np.datetime64("2026-08-15") + np.arange(42).astype("timedelta64[D]")
    for source_id, offset in (("gfs", 0.0), ("era5", 1.0), ("ifs", 2.0)):
        public_path = data / "forecasts" / source_id / f"{date}.json"
        public_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.write_text(
            json.dumps(
                {
                    "issue": {
                        "initialization": "2026-08-15T00:00:00Z",
                        "members": 5,
                        "initial_condition_source": {"id": source_id},
                    },
                    "grid": {"india_mask": [True, True, True, True]},
                }
            ),
            encoding="utf-8",
        )
        private_path = tmp_path / f"{source_id}.nc"
        values = np.ones((5, 42, 2, 2), dtype=np.float32) + offset
        xr.Dataset(
            {
                "tp": (("member", "lead_day", "latitude", "longitude"), values),
                "t2m": (("member", "lead_day", "latitude", "longitude"), values + 273.15),
            },
            coords={
                "member": np.arange(5),
                "lead_day": np.arange(42),
                "latitude": [1.5, 0.0],
                "longitude": [60.0, 61.5],
                "forecast_period_start": ("lead_day", starts),
                "forecast_period_end": ("lead_day", starts + np.timedelta64(1, "D")),
            },
        ).to_netcdf(private_path)
        paths[source_id] = private_path
    (data / "index.json").write_text("{}\n", encoding="utf-8")
    output = comparison.build(date, paths)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert set(payload["sources"]) == {"gfs", "era5", "ifs"}
    assert [pair["id"] for pair in payload["pairs"]] == [
        "ifs_minus_era5",
        "gfs_minus_era5",
        "ifs_minus_gfs",
    ]
    for source_id in payload["sources"]:
        forecast = json.loads(
            (data / "forecasts" / source_id / f"{date}.json").read_text()
        )
        assert forecast["issue"]["initialization_comparison"][
            "compared_source_ids"
        ] == ["gfs", "era5", "ifs"]
