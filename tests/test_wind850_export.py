"""Contract checks for published 850 hPa wind products."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import xarray as xr

from scripts.add_wind850_anomaly import (
    ANOMALY_PRODUCT,
    ANOMALY_PRODUCT_KEY,
    RAW_PRODUCT,
    RAW_PRODUCT_KEY,
    augment_wind_products,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("relative_path", "target", "left", "right", "weight", "members"),
    [
        ("era5/20260806.json", "0805", "0804", "0808", 0.25, 5),
        ("ifs/20260815.json", "0814", "0811", "0815", 0.75, 100),
    ],
)
def test_published_wind_anomaly_archive_remains_schema_compatible(
    relative_path: str,
    target: str,
    left: str,
    right: str,
    weight: float,
    members: int,
) -> None:
    forecast = json.loads(
        (ROOT / "public/data/forecasts" / relative_path).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (ROOT / "science/web-data.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(forecast)
    assert "wind850_anomaly" in forecast["products"]
    assert forecast["issue"]["capabilities"]["wind850_anomaly"] is True
    assert forecast["issue"]["members"] == members
    assert forecast["issue"]["wind850_climatology_alignment"] == {
        "status": "available",
        "target_model_state_calendar_day": target,
        "left_slot": left,
        "right_slot": right,
        "right_weight": weight,
        "operation_order": (
            "interpolate each yearly 51-member vector mean, aggregate seven "
            "lead days, then equally average 20 years"
        ),
    }
    for week_number, week in enumerate(forecast["weeks"], start=1):
        assert week["week"] == week_number
        speed = np.asarray(week["fields"]["wind850_anomaly"])
        u = np.asarray(week["vectors"]["wind850_anomaly"]["u"])
        v = np.asarray(week["vectors"]["wind850_anomaly"]["v"])
        assert speed.shape == u.shape == v.shape == (729,)
        assert np.isfinite(speed).all()
        assert np.isfinite(u).all()
        assert np.isfinite(v).all()
        assert np.hypot(u, v).max() > 0.1


def synthetic_inputs(
    tmp_path: Path, *, zero_member_spread: bool = False
) -> tuple[dict, Path, Path]:
    payload = json.loads(
        (ROOT / "public/data/forecasts/gfs/20260826.json").read_text(
            encoding="utf-8"
        )
    )
    payload["issue"]["initialization"] = "2026-08-28T00:00:00Z"
    payload["issue"]["information_cutoff"] = "2026-08-28T00:00:00Z"
    payload["issue"]["model_state_time"] = "2026-08-27T00:00:00Z"
    payload["issue"]["members"] = 2

    latitude = np.asarray(payload["grid"]["latitude"], dtype=np.float32)
    longitude = np.asarray(payload["grid"]["longitude"], dtype=np.float32)
    member_shape = (2, 42, 27, 27)
    u_forecast = np.empty(member_shape, dtype=np.float32)
    v_forecast = np.full(member_shape, 4.0, dtype=np.float32)
    u_forecast[0] = 3.0
    u_forecast[1] = 3.0 if zero_member_spread else -3.0
    forecast_path = tmp_path / "wind-forecast.nc"
    xr.Dataset(
        {
            "u850": (
                ("member", "lead_day", "latitude", "longitude"),
                u_forecast,
            ),
            "v850": (
                ("member", "lead_day", "latitude", "longitude"),
                v_forecast,
            ),
        },
        coords={
            "member": np.arange(2),
            "lead_day": np.arange(42),
            "latitude": latitude,
            "longitude": longitude,
            "forecast_reference_time": np.datetime64(
                "2026-08-28T00:00:00", "ns"
            ),
            "model_state_time": np.datetime64("2026-08-27T00:00:00", "ns"),
        },
    ).to_netcdf(forecast_path)

    climatology_shape = (2, 20, 42, 27, 27)
    u_climatology = np.empty(climatology_shape, dtype=np.float32)
    v_climatology = np.empty(climatology_shape, dtype=np.float32)
    u_climatology[0] = -2.0
    u_climatology[1] = 0.0
    v_climatology[0] = 1.0
    v_climatology[1] = 3.0
    climatology_path = tmp_path / "wind-climatology.nc"
    xr.Dataset(
        {
            "u850_ensemble_mean": (
                (
                    "init_slot",
                    "hindcast_year",
                    "lead_day",
                    "latitude",
                    "longitude",
                ),
                u_climatology,
            ),
            "v850_ensemble_mean": (
                (
                    "init_slot",
                    "hindcast_year",
                    "lead_day",
                    "latitude",
                    "longitude",
                ),
                v_climatology,
            ),
        },
        coords={
            "init_slot": ["0825", "0829"],
            "hindcast_year": np.arange(2002, 2022),
            "lead_day": np.arange(42),
            "latitude": latitude,
            "longitude": longitude,
        },
    ).to_netcdf(climatology_path)
    return payload, forecast_path, climatology_path


def test_exporter_adds_mean_and_anomalous_wind_with_matched_vectors(
    tmp_path: Path,
) -> None:
    payload, forecast_path, climatology_path = synthetic_inputs(tmp_path)

    result = augment_wind_products(payload, forecast_path, climatology_path)

    assert list(result["products"])[-2:] == [
        RAW_PRODUCT_KEY,
        ANOMALY_PRODUCT_KEY,
    ]
    assert result["products"][RAW_PRODUCT_KEY] == RAW_PRODUCT
    assert result["products"][ANOMALY_PRODUCT_KEY] == ANOMALY_PRODUCT
    assert result["issue"]["available_products"] == list(result["products"])
    assert result["issue"]["capabilities"][RAW_PRODUCT_KEY] is True
    assert result["issue"]["capabilities"][ANOMALY_PRODUCT_KEY] is True
    assert result["issue"]["wind850_climatology_alignment"] == {
        "status": "available",
        "target_model_state_calendar_day": "0827",
        "left_slot": "0825",
        "right_slot": "0829",
        "right_weight": 0.5,
        "operation_order": (
            "interpolate each yearly 51-member vector mean, aggregate seven "
            "lead days, then equally average 20 years"
        ),
    }

    provenance = result["issue"]["wind850_provenance"]
    assert provenance["forecast_members"] == 2
    assert provenance["hindcast_years"] == list(range(2002, 2022))
    assert set(provenance["definitions"]) == {
        RAW_PRODUCT_KEY,
        ANOMALY_PRODUCT_KEY,
    }
    assert len(provenance["forecast_sha256"]) == 64
    assert len(provenance["climatology_sha256"]) == 64

    expected_anomaly = 4.0 - np.sqrt(5.0)
    for week in result["weeks"]:
        np.testing.assert_allclose(week["fields"][RAW_PRODUCT_KEY], 4.0)
        np.testing.assert_allclose(
            week["vectors"][RAW_PRODUCT_KEY]["u"], 0.0
        )
        np.testing.assert_allclose(
            week["vectors"][RAW_PRODUCT_KEY]["v"], 4.0
        )
        np.testing.assert_allclose(
            week["fields"][ANOMALY_PRODUCT_KEY], expected_anomaly, atol=5e-5
        )
        np.testing.assert_allclose(
            week["vectors"][ANOMALY_PRODUCT_KEY]["u"], 1.0
        )
        np.testing.assert_allclose(
            week["vectors"][ANOMALY_PRODUCT_KEY]["v"], 2.0
        )

    diagnostics = result["diagnostics"]
    assert diagnostics["wind850_weekly_component_spread_max_m_s"] == 3.0
    assert diagnostics["wind850_mean_speed_min_m_s"] == 4.0
    assert diagnostics["wind850_mean_speed_max_m_s"] == 4.0
    assert diagnostics["wind850_speed_anomaly_min_m_s"] == round(
        expected_anomaly, 4
    )
    assert diagnostics["wind850_speed_anomaly_max_m_s"] == round(
        expected_anomaly, 4
    )


def test_exporter_rejects_multi_member_forecast_with_zero_spread(
    tmp_path: Path,
) -> None:
    payload, forecast_path, climatology_path = synthetic_inputs(
        tmp_path, zero_member_spread=True
    )

    with pytest.raises(ValueError, match="zero member spread"):
        augment_wind_products(payload, forecast_path, climatology_path)
