"""Contract checks for published 850 hPa wind-anomaly products."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("relative_path", "target", "left", "right", "weight", "members"),
    [
        ("era5/20260806.json", "0805", "0804", "0808", 0.25, 5),
        ("ifs/20260815.json", "0814", "0811", "0815", 0.75, 100),
    ],
)
def test_wind_anomaly_has_six_weekly_scalar_and_vector_fields(
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
