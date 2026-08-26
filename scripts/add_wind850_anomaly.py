#!/usr/bin/env python3
"""Add weekly mean and anomalous 850 hPa wind to an India forecast issue."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr


RAW_PRODUCT_KEY = "wind850_mean"
ANOMALY_PRODUCT_KEY = "wind850_anomaly"
# Backward-compatible aliases for callers that imported the original constants.
PRODUCT_KEY = ANOMALY_PRODUCT_KEY

RAW_PRODUCT = {
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

ANOMALY_PRODUCT = {
    "label": "850 hPa wind anomaly",
    "short_label": "850 hPa wind anomaly",
    "description": (
        "Shading is the weekly-mean wind-speed anomaly; arrows are the "
        "weekly U/V vector-component anomaly"
    ),
    "units": "m s-1",
    "baseline": "Native model reforecasts, 2002–2021",
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
# Preserve the original exported constant name.
PRODUCT = ANOMALY_PRODUCT

FORECAST_DIMS = ("member", "lead_day", "latitude", "longitude")
CLIMATOLOGY_DIMS = (
    "init_slot",
    "hindcast_year",
    "lead_day",
    "latitude",
    "longitude",
)
MAX_PLAUSIBLE_WIND_SPEED_M_S = 100.0


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


def ordered_values(
    variable: xr.DataArray, expected_dims: tuple[str, ...], label: str
) -> np.ndarray:
    if set(variable.dims) != set(expected_dims) or len(variable.dims) != len(
        expected_dims
    ):
        raise ValueError(
            f"{label} dimensions are {variable.dims}, expected {expected_dims}"
        )
    values = np.asarray(variable.transpose(*expected_dims).values, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} contains non-finite values")
    return values


def augment_wind_products(
    payload: dict[str, Any], wind_forecast: Path, wind_climatology: Path
) -> dict[str, Any]:
    """Augment ``payload`` with weekly raw and anomalous U850/V850 products."""

    issue = payload["issue"]
    products = payload["products"]
    weeks = payload["weeks"]
    if not isinstance(products, dict):
        raise ValueError("public forecast products must be an object")
    if not isinstance(weeks, list) or len(weeks) != 6:
        raise ValueError("public forecast must contain exactly six weeks")
    for expected_week, week in enumerate(weeks, start=1):
        if not isinstance(week, dict) or week.get("week") != expected_week:
            raise ValueError("public forecast weeks are not ordered one through six")
        if not isinstance(week.get("fields"), dict) or not isinstance(
            week.get("summary"), dict
        ):
            raise ValueError(f"public forecast week {expected_week} is incomplete")
        if "vectors" in week and not isinstance(week["vectors"], dict):
            raise ValueError(f"public forecast week {expected_week} vectors are invalid")
    capabilities = issue.setdefault("capabilities", {})
    if not isinstance(capabilities, dict):
        raise ValueError("public forecast capabilities must be an object")

    latitude = np.asarray(payload["grid"]["latitude"], dtype=np.float64)
    longitude = np.asarray(payload["grid"]["longitude"], dtype=np.float64)
    if latitude.shape != (27,) or longitude.shape != (27,):
        raise ValueError("public forecast is not on the 27 by 27 India grid")
    mask = np.asarray(payload["grid"]["india_mask"], dtype=bool)
    if mask.size != 27 * 27:
        raise ValueError("public forecast India support mask has the wrong size")
    mask = mask.reshape(27, 27)
    if int(mask.sum()) <= 0 or int(mask.sum()) != int(
        payload["grid"]["supported_cell_count"]
    ):
        raise ValueError("India support mask count is inconsistent")

    with xr.open_dataset(wind_forecast) as forecast:
        if set(("u850", "v850")) - set(forecast.data_vars):
            raise ValueError("wind forecast lacks U850/V850")
        if forecast.sizes.get("member") != int(issue["members"]):
            raise ValueError("wind member count differs from the public issue")
        if forecast.sizes.get("lead_day") != 42:
            raise ValueError("wind forecast must contain 42 lead days")
        if issue_day(issue["initialization"]) != (
            forecast.forecast_reference_time.values.astype("datetime64[D]")
        ):
            raise ValueError("wind forecast initialization differs from the public issue")
        if issue_day(issue["model_state_time"]) != (
            forecast.model_state_time.values.astype("datetime64[D]")
        ):
            raise ValueError("wind model-state time differs from the public issue")
        if not np.array_equal(forecast.latitude.values, latitude.astype(np.float32)):
            raise ValueError("wind latitude differs from the public issue")
        if not np.array_equal(forecast.longitude.values, longitude.astype(np.float32)):
            raise ValueError("wind longitude differs from the public issue")
        u_members = weekly_mean(
            ordered_values(forecast.u850, FORECAST_DIMS, "forecast U850")
        )
        v_members = weekly_mean(
            ordered_values(forecast.v850, FORECAST_DIMS, "forecast V850")
        )

    target = issue["model_state_time"][5:10].replace("-", "")
    with xr.open_dataset(wind_climatology) as climatology:
        if set(("u850_ensemble_mean", "v850_ensemble_mean")) - set(
            climatology.data_vars
        ):
            raise ValueError("wind climatology lacks ensemble-mean U850/V850")
        if not np.array_equal(climatology.latitude.values, latitude.astype(np.float32)):
            raise ValueError("wind climatology latitude differs from the public issue")
        if not np.array_equal(climatology.longitude.values, longitude.astype(np.float32)):
            raise ValueError("wind climatology longitude differs from the public issue")
        years = climatology.hindcast_year.values.astype(int)
        if years.tolist() != list(range(2002, 2022)):
            raise ValueError("wind climatology must contain exactly 2002-2021")
        if climatology.sizes.get("lead_day") != 42:
            raise ValueError("wind climatology must contain 42 lead days")
        left, right, right_weight = bracket(climatology.init_slot.values, target)
        u_climatology = ordered_values(
            climatology.u850_ensemble_mean,
            CLIMATOLOGY_DIMS,
            "climatology U850",
        )
        v_climatology = ordered_values(
            climatology.v850_ensemble_mean,
            CLIMATOLOGY_DIMS,
            "climatology V850",
        )
        slot_labels = [str(value) for value in climatology.init_slot.values]
        left_index = slot_labels.index(left)
        right_index = slot_labels.index(right)
        u_daily = (
            u_climatology[left_index] * (1.0 - right_weight)
            + u_climatology[right_index] * right_weight
        )
        v_daily = (
            v_climatology[left_index] * (1.0 - right_weight)
            + v_climatology[right_index] * right_weight
        )

    u_history = weekly_mean(u_daily)
    v_history = weekly_mean(v_daily)
    u_mean = u_members.mean(axis=0)
    v_mean = v_members.mean(axis=0)
    speed_mean = np.hypot(u_mean, v_mean)
    member_speed = np.hypot(u_members, v_members)
    history_speed = np.hypot(u_history, v_history)
    u_anomaly = u_mean - u_history.mean(axis=0)
    v_anomaly = v_mean - v_history.mean(axis=0)
    speed_anomaly = speed_mean - history_speed.mean(axis=0)
    if not all(
        np.isfinite(values).all()
        for values in (
            u_mean,
            v_mean,
            speed_mean,
            u_anomaly,
            v_anomaly,
            speed_anomaly,
        )
    ):
        raise ValueError("derived wind product contains non-finite values")
    if max(float(member_speed.max()), float(history_speed.max())) > (
        MAX_PLAUSIBLE_WIND_SPEED_M_S
    ):
        raise ValueError(
            "weekly forecast or climatological 850 hPa wind exceeds 100 m/s"
        )

    component_spread = np.hypot(
        u_members.std(axis=0, ddof=0), v_members.std(axis=0, ddof=0)
    )
    if int(issue["members"]) > 1 and float(component_spread.max()) <= 0.0:
        raise ValueError("wind forecast has zero member spread")

    # Removing first keeps product ordering deterministic when regenerating an
    # issue that already contains the anomaly-only legacy representation.
    products.pop(RAW_PRODUCT_KEY, None)
    products.pop(ANOMALY_PRODUCT_KEY, None)
    products[RAW_PRODUCT_KEY] = copy.deepcopy(RAW_PRODUCT)
    products[ANOMALY_PRODUCT_KEY] = copy.deepcopy(ANOMALY_PRODUCT)
    for index, week in enumerate(weeks):
        fields = week["fields"]
        summaries = week["summary"]
        vectors = week.setdefault("vectors", {})
        for product_key in (RAW_PRODUCT_KEY, ANOMALY_PRODUCT_KEY):
            fields.pop(product_key, None)
            summaries.pop(product_key, None)
            vectors.pop(product_key, None)
        fields[RAW_PRODUCT_KEY] = flatten(speed_mean[index])
        summaries[RAW_PRODUCT_KEY] = summary(speed_mean[index], mask, latitude)
        vectors[RAW_PRODUCT_KEY] = {
            "u": flatten(u_mean[index]),
            "v": flatten(v_mean[index]),
        }
        fields[ANOMALY_PRODUCT_KEY] = flatten(speed_anomaly[index])
        summaries[ANOMALY_PRODUCT_KEY] = summary(
            speed_anomaly[index], mask, latitude
        )
        vectors[ANOMALY_PRODUCT_KEY] = {
            "u": flatten(u_anomaly[index]),
            "v": flatten(v_anomaly[index]),
        }

    issue["available_products"] = list(products)
    capabilities[RAW_PRODUCT_KEY] = True
    capabilities[ANOMALY_PRODUCT_KEY] = True
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
        "forecast_sha256": sha256(wind_forecast),
        "climatology_sha256": sha256(wind_climatology),
        "definitions": {
            RAW_PRODUCT_KEY: (
                "shading: speed computed from the weekly ensemble-mean U/V "
                "components; arrows: the same weekly ensemble-mean U/V components"
            ),
            ANOMALY_PRODUCT_KEY: (
                "shading: ensemble-mean vector speed minus the equally weighted "
                "mean of 20 yearly vector speeds; arrows: forecast U/V mean minus "
                "the 2002-2021 U/V model climatology"
            ),
        },
        # Keep the original field for anomaly-only consumers.
        "definition": (
            "shading: ensemble-mean vector speed minus the equally weighted "
            "mean of 20 yearly vector speeds; arrows: forecast U/V mean minus "
            "the 2002-2021 U/V model climatology"
        ),
    }
    diagnostics = payload.setdefault("diagnostics", {})
    diagnostics["wind850_weekly_component_spread_max_m_s"] = round(
        float(component_spread.max()), 4
    )
    diagnostics["wind850_mean_speed_min_m_s"] = round(float(speed_mean.min()), 4)
    diagnostics["wind850_mean_speed_max_m_s"] = round(float(speed_mean.max()), 4)
    diagnostics["wind850_speed_anomaly_min_m_s"] = round(
        float(speed_anomaly.min()), 4
    )
    diagnostics["wind850_speed_anomaly_max_m_s"] = round(
        float(speed_anomaly.max()), 4
    )
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    return payload


def main() -> int:
    args = parse_args()
    output = args.output or args.forecast_json
    payload: dict[str, Any] = json.loads(
        args.forecast_json.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON constant: {value}")
        ),
    )
    payload = augment_wind_products(
        payload, args.wind_forecast, args.wind_climatology
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        f"wrote {output} with six weekly mean and anomalous wind fields and vectors",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
