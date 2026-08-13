"""Contract checks for the 6 August limited-member wind-anomaly product."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FORECAST = ROOT / "public/data/forecasts/era5/20260806.json"


def test_august_6_wind_anomaly_has_six_weekly_scalar_and_vector_fields() -> None:
    forecast = json.loads(FORECAST.read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "science/web-data.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(forecast)
    assert "wind850_anomaly" in forecast["products"]
    assert forecast["issue"]["capabilities"]["wind850_anomaly"] is True
    assert forecast["issue"]["wind850_climatology_alignment"] == {
        "status": "available",
        "target_model_state_calendar_day": "0805",
        "left_slot": "0804",
        "right_slot": "0808",
        "right_weight": 0.25,
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
