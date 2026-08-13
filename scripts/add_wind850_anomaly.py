#!/usr/bin/env python3
"""Add weekly 850 hPa wind anomalies to one compact India forecast issue."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr


PRODUCT_KEY = "wind850_anomaly"
PRODUCT = {
    "label": "850 hPa wind anomaly",
    "short_label": "850 hPa wind anomaly",
    "description": (
        "Shading is the weekly-mean wind-speed anomaly; arrows are the "
        "weekly U/V vector-component anomaly"
    ),
    "units": "m s-1",
    "baseline": "FuXi-S2S native reforecasts, 2002–2021",
    "legend": {
        "boundaries": [-8, -6, -4, -2, -1, 1, 2, 4, 6, 8],
        "colors": [
            "#6f321e",
            "#a8552f",
            "#d98b57",
            "#efc79f",
            "#f7f5ef",
            "#c9e2ee",
            "#83bdd4",
            "#3988b2",
            "#14567f",
        ],
        "under": "#421c12",
        "over": "#083653",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast-json", type=Path, required=True)
    parser.add_argument("--wind-forecast", type=Path, required=True)
    parser.add_argument("--wind-climatology", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def weekly_mean(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape[-3] != 42:
        raise ValueError(f"wind field has {array.shape[-3]} lead days, expected 42")
    return array.reshape(*array.shape[:-3], 6, 7, *array.shape[-2:]).mean(axis=-3)


def bracket(slots: np.ndarray, target: str) -> tuple[str, str, float]:
    labels = sorted(str(value) for value in slots)
    target_date = np.datetime64(f"2000-{target[:2]}-{target[2:]}")
    dates = np.asarray(
        [np.datetime64(f"2000-{value[:2]}-{value[2:]}") for value in labels]
    )
    matches = np.flatnonzero(dates == target_date)
    if matches.size:
        label = labels[int(matches[0])]
        return label, label, 0.0
    insertion = int(np.searchsorted(dates, target_date))
    if insertion == 0 or insertion == len(dates):
        raise ValueError(f"{target} is outside the wind climatology")
    left_date, right_date = dates[insertion - 1], dates[insertion]
    weight = float((target_date - left_date) / (right_date - left_date))
    return labels[insertion - 1], labels[insertion], weight


def flatten(values: np.ndarray) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != (27, 27) or not np.isfinite(array).all():
        raise ValueError(f"invalid public wind field shape {array.shape}")
    return np.round(array, 4).ravel().tolist()


def summary(
    values: np.ndarray, mask: np.ndarray, latitude: np.ndarray
) -> dict[str, float]:
    weights = np.cos(np.deg2rad(latitude))[:, None] * mask
    supported = values[mask]
    return {
        "india_weighted_mean": round(float(np.sum(values * weights) / weights.sum()), 3),
        "india_minimum": round(float(supported.min()), 3),
        "india_maximum": round(float(supported.max()), 3),
    }


def issue_day(value: str) -> np.datetime64:
    return np.datetime64(value[:10], "D")


def main() -> int:
    args = parse_args()
    output = args.output or args.forecast_json
    payload: dict[str, Any] = json.loads(
        args.forecast_json.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON constant: {value}")
        ),
    )
    issue = payload["issue"]
    latitude = np.asarray(payload["grid"]["latitude"], dtype=np.float64)
    longitude = np.asarray(payload["grid"]["longitude"], dtype=np.float64)
    mask = np.asarray(payload["grid"]["india_mask"], dtype=bool).reshape(27, 27)
    if latitude.shape != (27,) or longitude.shape != (27,):
        raise ValueError("public forecast is not on the 27 by 27 India grid")
    if int(mask.sum()) != int(payload["grid"]["supported_cell_count"]):
        raise ValueError("India support mask count is inconsistent")

    with xr.open_dataset(args.wind_forecast) as forecast:
        if set(("u850", "v850")) - set(forecast.data_vars):
            raise ValueError("wind forecast lacks U850/V850")
        if forecast.sizes.get("member") != int(issue["members"]):
            raise ValueError("wind member count differs from the public issue")
        if forecast.sizes.get("lead_day") != 42:
            raise ValueError("wind forecast must contain 42 lead days")
        if issue_day(issue["initialization"]) != forecast.forecast_reference_time.values.astype("datetime64[D]"):
            raise ValueError("wind forecast initialization differs from the public issue")
        if issue_day(issue["model_state_time"]) != forecast.model_state_time.values.astype("datetime64[D]"):
            raise ValueError("wind model-state time differs from the public issue")
        if not np.array_equal(forecast.latitude.values, latitude.astype(np.float32)):
            raise ValueError("wind latitude differs from the public issue")
        if not np.array_equal(forecast.longitude.values, longitude.astype(np.float32)):
            raise ValueError("wind longitude differs from the public issue")
        u_members = weekly_mean(forecast.u850.values)
        v_members = weekly_mean(forecast.v850.values)

    target = issue["model_state_time"][5:10].replace("-", "")
    with xr.open_dataset(args.wind_climatology) as climatology:
        if not np.array_equal(climatology.latitude.values, latitude.astype(np.float32)):
            raise ValueError("wind climatology latitude differs from the public issue")
        if not np.array_equal(climatology.longitude.values, longitude.astype(np.float32)):
            raise ValueError("wind climatology longitude differs from the public issue")
        years = climatology.hindcast_year.values.astype(int)
        if years.tolist() != list(range(2002, 2022)):
            raise ValueError("wind climatology must contain exactly 2002-2021")
        left, right, right_weight = bracket(climatology.init_slot.values, target)
        u_daily = (
            climatology.u850_ensemble_mean.sel(init_slot=left).values
            * (1.0 - right_weight)
            + climatology.u850_ensemble_mean.sel(init_slot=right).values
            * right_weight
        )
        v_daily = (
            climatology.v850_ensemble_mean.sel(init_slot=left).values
            * (1.0 - right_weight)
            + climatology.v850_ensemble_mean.sel(init_slot=right).values
            * right_weight
        )

    u_history = weekly_mean(u_daily)
    v_history = weekly_mean(v_daily)
    u_mean = u_members.mean(axis=0)
    v_mean = v_members.mean(axis=0)
    u_anomaly = u_mean - u_history.mean(axis=0)
    v_anomaly = v_mean - v_history.mean(axis=0)
    speed_anomaly = np.hypot(u_mean, v_mean) - np.hypot(u_history, v_history).mean(axis=0)
    if not all(
        np.isfinite(values).all()
        for values in (u_anomaly, v_anomaly, speed_anomaly)
    ):
        raise ValueError("derived wind anomaly contains non-finite values")

    payload["products"][PRODUCT_KEY] = PRODUCT
    for index, week in enumerate(payload["weeks"]):
        week["fields"][PRODUCT_KEY] = flatten(speed_anomaly[index])
        week["summary"][PRODUCT_KEY] = summary(
            speed_anomaly[index], mask, latitude
        )
        vectors = week.setdefault("vectors", {})
        vectors[PRODUCT_KEY] = {
            "u": flatten(u_anomaly[index]),
            "v": flatten(v_anomaly[index]),
        }

    issue["available_products"] = list(payload["products"])
    issue.setdefault("capabilities", {})[PRODUCT_KEY] = True
    issue["wind850_climatology_alignment"] = {
        "status": "available",
        "target_model_state_calendar_day": target,
        "left_slot": left,
        "right_slot": right,
        "right_weight": right_weight,
        "operation_order": (
            "interpolate each yearly 51-member vector mean, aggregate seven "
            "lead days, then equally average 20 years"
        ),
    }
    issue["wind850_provenance"] = {
        "forecast_members": int(issue["members"]),
        "hindcast_years": years.tolist(),
        "native_members_per_hindcast_year": 51,
        "forecast_sha256": sha256(args.wind_forecast),
        "climatology_sha256": sha256(args.wind_climatology),
        "definition": (
            "shading: ensemble-mean vector speed minus the equally weighted "
            "mean of 20 yearly vector speeds; arrows: forecast U/V mean minus "
            "the 2002-2021 U/V model climatology"
        ),
    }
    component_spread = np.hypot(
        u_members.std(axis=0, ddof=0), v_members.std(axis=0, ddof=0)
    )
    payload.setdefault("diagnostics", {})[
        "wind850_weekly_component_spread_max_m_s"
    ] = round(float(component_spread.max()), 4)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        f"wrote {output} with six weekly wind-anomaly fields and vectors",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
