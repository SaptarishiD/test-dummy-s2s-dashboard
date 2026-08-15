from __future__ import annotations

import pytest
import numpy as np
import xarray as xr
import json
import jsonschema
from pathlib import Path

from scripts.build_custom_domain import forecast_payload, validate_config


def test_custom_domain_accepts_grid_aligned_bbox() -> None:
    result = validate_config(
        {
            "id": "east-africa",
            "label": "East Africa",
            "bounds": {"north": 21, "south": -15, "west": 22.5, "east": 52.5},
            "products": ["rainfall_total", "temperature_mean"],
            "pdf": True,
        }
    )
    assert result["kind"] == "configured_bbox"
    assert result["pdf"] is True


@pytest.mark.parametrize(
    "bounds, message",
    [
        ({"north": 20, "south": -15, "west": 22.5, "east": 52.5}, "aligned"),
        ({"north": -15, "south": 21, "west": 22.5, "east": 52.5}, "latitude"),
        ({"north": 21, "south": -15, "west": 170, "east": -170}, "longitude"),
    ],
)
def test_custom_domain_rejects_unsupported_bounds(bounds: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_config({"id": "test-box", "label": "Test", "bounds": bounds})


def test_custom_domain_exports_dynamic_raw_grid(tmp_path) -> None:
    domain = validate_config(
        {
            "id": "small-box",
            "label": "Small Box",
            "bounds": {"north": 3, "south": 0, "west": 60, "east": 63},
        }
    )
    latitude = np.array([3.0, 1.5, 0.0])
    longitude = np.array([60.0, 61.5, 63.0])
    leads = np.arange(42)
    values = np.ones((5, 42, 3, 3), dtype=np.float32)
    start = np.datetime64("2026-08-15") + leads.astype("timedelta64[D]")
    path = tmp_path / "forecast.nc"
    xr.Dataset(
        {
            "tp": (("member", "lead_day", "latitude", "longitude"), values),
            "t2m": (("member", "lead_day", "latitude", "longitude"), values * 300),
        },
        coords={
            "member": np.arange(5),
            "lead_day": leads,
            "latitude": latitude,
            "longitude": longitude,
            "forecast_period_start": ("lead_day", start),
            "forecast_period_end": ("lead_day", start + np.timedelta64(1, "D")),
            "forecast_reference_time": np.datetime64("2026-08-15"),
            "model_state_time": np.datetime64("2026-08-14"),
        },
        attrs={"input_source": "GFS test input"},
    ).to_netcdf(path)
    payload, issue_id = forecast_payload(path, "gfs", domain)
    assert issue_id == "20260815"
    assert payload["schema_version"] == 2
    assert payload["grid"]["shape"] == [3, 3]
    assert set(payload["products"]) == {"rainfall_total", "temperature_mean"}
    assert len(payload["weeks"]) == 6
    assert len(payload["weeks"][0]["fields"]["rainfall_total"]) == 9
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "science/web-data.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(payload)
