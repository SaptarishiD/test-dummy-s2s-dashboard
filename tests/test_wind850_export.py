"""Contract checks for published 850 hPa wind products."""

from __future__ import annotations

import copy
import json
import re
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

from scripts import build_forecast_pdfs as pdf_builder
from scripts.validate_web_data import validate_wind_contract


ROOT = Path(__file__).resolve().parents[1]


def with_raw_wind(forecast: dict) -> dict:
    """Return a representative six-product payload without changing fixtures."""

    payload = copy.deepcopy(forecast)
    payload["products"]["wind850_mean"] = {
        "label": "Weekly mean 850 hPa wind",
        "short_label": "850 hPa wind",
        "description": (
            "Shading is the speed of the weekly ensemble-mean wind vector; "
            "arrows are the weekly ensemble-mean U/V components"
        ),
        "units": "m/s",
        "baseline": None,
        "legend": {
            "boundaries": [0, 3, 6, 9, 12, 18, 25, 35],
            "colors": [
                "#10212b",
                "#194554",
                "#1d7180",
                "#36a09b",
                "#8ac483",
                "#e1c969",
                "#e8804c",
            ],
            "under": "#09171e",
            "over": "#d84e43",
        },
    }
    payload["issue"]["available_products"] = list(payload["products"])
    payload["issue"].setdefault("capabilities", {})["wind850_mean"] = True
    for week in payload["weeks"]:
        anomaly = week["vectors"]["wind850_anomaly"]
        u = np.asarray(anomaly["u"], dtype=np.float64) + 6.0
        v = np.asarray(anomaly["v"], dtype=np.float64) + 3.0
        speed = np.hypot(u, v)
        week["fields"]["wind850_mean"] = speed.tolist()
        week["summary"]["wind850_mean"] = {
            "india_weighted_mean": float(speed.mean()),
            "india_minimum": float(speed.min()),
            "india_maximum": float(speed.max()),
        }
        week["vectors"]["wind850_mean"] = {"u": u.tolist(), "v": v.tolist()}
    return payload


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
    validate_wind_contract(
        forecast,
        {"wind850_anomaly": True},
        relative_path.removesuffix(".json"),
    )
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


def test_schema_and_web_validator_accept_raw_and_anomalous_wind() -> None:
    legacy = json.loads(
        (ROOT / "public/data/forecasts/ifs/20260819.json").read_text(
            encoding="utf-8"
        )
    )
    forecast = with_raw_wind(legacy)
    schema = json.loads(
        (ROOT / "science/web-data.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(forecast)
    validate_wind_contract(
        forecast,
        {"wind850_mean": True, "wind850_anomaly": True},
        "ifs/20260819",
    )
    assert len(forecast["products"]) == 6
    for week in forecast["weeks"]:
        assert set(week["vectors"]) == {"wind850_mean", "wind850_anomaly"}
        assert min(week["fields"]["wind850_mean"]) >= 0


def test_pdf_builder_creates_one_page_for_each_of_six_products(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forecast = with_raw_wind(
        json.loads(
            (ROOT / "public/data/forecasts/ifs/20260819.json").read_text(
                encoding="utf-8"
            )
        )
    )
    temporary_public = tmp_path / "public"
    forecast_path = temporary_public / "data/forecasts/ifs/20260819.json"
    forecast_path.parent.mkdir(parents=True)
    forecast_path.write_text(json.dumps(forecast), encoding="utf-8")
    monkeypatch.setattr(pdf_builder, "PUBLIC", temporary_public)
    data = ROOT / "public/data"
    output = pdf_builder.build_pdf(
        forecast_path,
        {"id": "ifs"},
        {"id": "20260819"},
        json.loads((data / "world-countries.geojson").read_text(encoding="utf-8")),
        json.loads((data / "india-outline.json").read_text(encoding="utf-8")),
        json.loads((data / "india-admin.json").read_text(encoding="utf-8")),
    )
    pdf_bytes = output.read_bytes()
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type /Page\b", pdf_bytes)) == 6
