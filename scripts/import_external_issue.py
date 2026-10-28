#!/usr/bin/env python3
"""Import an externally produced FuXi weekly package as a compact public issue.

This is the manual fallback used when the cluster export pipeline is
unavailable.  It reads the ``weekly.nc`` and ``anomaly_weekly.nc`` files of a
FuXi report package (any member count, any 1.5-degree sub-grid of the India
grid), embeds them in the published 27x27 India grid, and writes a schema-v3
forecast JSON carrying only what the package supports: raw weekly rainfall,
temperature and 850 hPa wind, plus rainfall/temperature anomalies against the
package's ERA5 calendar-day climatology.  Wind anomalies, extremes and regional
probabilities are withheld because no model climatology is available.

Cells outside the package domain are written as finite placeholders and marked
false in ``grid.coverage_mask``; the frontend hatches them as unavailable.

No NetCDF attribute is copied, because the packages embed private host paths.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science.formulas import (  # noqa: E402
    area_weights,
    ensemble_mean,
    forecast_spread,
    weighted_mean,
    wind_speed,
)
from science.validators import write_json  # noqa: E402

DATA = ROOT / "public" / "data"
WEEKS = 6
PLACEHOLDER = 0.0
ERA5_BASELINE = (
    "ERA5 reanalysis, 2011–2025 calendar-day climatology (includes model bias)"
)
RAW_KEYS = ("rainfall_total", "temperature_mean", "wind850_mean")
ANOMALY_KEYS = ("rainfall_anomaly", "temperature_anomaly")
SOURCE_BLOCKS = {
    "ifs": {
        "label": "IFS operational initialization",
        "short_label": "IFS",
        "category": "operational_initialization",
        "availability": "near_real_time",
        "description": (
            "Operational ECMWF IFS fields aggregated into the model's two daily "
            "input states. Ocean skin temperature is used as the disclosed SST "
            "proxy. Experimental."
        ),
        "id": "ifs",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten(values: np.ndarray) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("derived field contains non-finite values")
    return np.round(array, 4).ravel().tolist()


def summary(values: np.ndarray, mask: np.ndarray, latitude: np.ndarray) -> dict[str, float]:
    weights = area_weights(latitude, mask.astype(np.float64))
    supported = values[mask]
    return {
        "india_weighted_mean": round(weighted_mean(values, weights), 3),
        "india_minimum": round(float(supported.min()), 3),
        "india_maximum": round(float(supported.max()), 3),
    }


def subgrid_indices(target: np.ndarray, source: np.ndarray, name: str) -> np.ndarray:
    indices = []
    for value in source:
        match = np.flatnonzero(np.isclose(target, value, atol=1e-6))
        if match.size != 1:
            raise ValueError(f"{name} {value} is not on the published grid")
        indices.append(int(match[0]))
    if np.any(np.diff(indices) != 1):
        raise ValueError(f"{name} is not a contiguous published sub-grid")
    return np.asarray(indices)


def embed(values: np.ndarray, rows: np.ndarray, columns: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    full = np.full(values.shape[:-2] + shape, PLACEHOLDER, dtype=np.float64)
    full[..., rows[0]:rows[-1] + 1, columns[0]:columns[-1] + 1] = values
    return full


def week_dates(dataset: xr.Dataset, initialization: date) -> list[tuple[str, str]]:
    starts = dataset["valid_start"].values.astype("datetime64[D]").astype(str)
    ends = dataset["valid_end"].values.astype("datetime64[D]")
    dates = []
    for index in range(WEEKS):
        start = date.fromisoformat(str(starts[index]))
        # Packages use an exclusive end; the site publishes the inclusive last day.
        end = date.fromisoformat(str((ends[index] - np.timedelta64(1, "D")).astype(str)))
        if start != initialization + timedelta(days=7 * index) or (end - start).days != 6:
            raise ValueError(f"week {index + 1} is not a complete seven-day week")
        dates.append((start.isoformat(), end.isoformat()))
    return dates


def product_definitions(template: dict[str, Any], members: int) -> dict[str, Any]:
    products: dict[str, Any] = {}
    for key in (*RAW_KEYS[:2], *ANOMALY_KEYS, RAW_KEYS[2]):
        definition = copy.deepcopy(template["products"][key])
        definition["description"] = definition["description"].replace(
            "100-member", f"{members}-member"
        )
        if key in ANOMALY_KEYS:
            definition["description"] = (
                "Weekly-mean forecast minus the ERA5 calendar-day climatology"
            )
            definition["baseline"] = ERA5_BASELINE
        products[key] = definition
    return products


def build(args: argparse.Namespace) -> dict[str, Any]:
    template = load_json(args.template)
    grid = template["grid"]
    latitude = np.asarray(grid["latitude"], dtype=np.float64)
    longitude = np.asarray(grid["longitude"], dtype=np.float64)
    shape = (latitude.size, longitude.size)
    mask = np.asarray(grid["india_mask"], dtype=bool).reshape(shape)

    weekly = xr.open_dataset(args.weekly)
    anomalies = xr.open_dataset(args.anomaly)
    initialization = date.fromisoformat(str(weekly.attrs["init"]))
    if initialization.strftime("%Y%m%d") != args.issue:
        raise ValueError(f"package initialization {initialization} is not {args.issue}")
    if str(weekly.attrs.get("source")) != args.source:
        raise ValueError(f"package source is not {args.source}")
    if anomalies.attrs.get("baseline_kind") != "era5_climatology":
        raise ValueError("anomaly package is not an ERA5-climatology baseline")
    for dataset in (weekly, anomalies):
        if dataset.sizes["lead_week"] != WEEKS:
            raise ValueError("package must contain six lead weeks")
    if not np.array_equal(weekly["lat"], anomalies["lat"]) or not np.array_equal(
        weekly["lon"], anomalies["lon"]
    ):
        raise ValueError("weekly and anomaly packages use different grids")
    dates = week_dates(weekly, initialization)
    if dates != week_dates(anomalies, initialization):
        raise ValueError("weekly and anomaly packages use different weeks")

    rows = subgrid_indices(latitude, weekly["lat"].values, "latitude")
    columns = subgrid_indices(longitude, weekly["lon"].values, "longitude")
    coverage = embed(np.ones((rows.size, columns.size)), rows, columns, shape) > 0.5
    if np.any(mask & ~coverage):
        raise ValueError("package domain does not cover every India-mask cell")
    members = int(weekly.sizes["member"])

    def members_first(dataset: xr.Dataset, name: str) -> np.ndarray:
        values = dataset[name].transpose("member", "lead_week", "lat", "lon").values
        values = np.asarray(values, dtype=np.float64)
        if not np.isfinite(values).all():
            raise ValueError(f"{name} contains non-finite values")
        return values

    rain_members = members_first(weekly, "tp")  # weekly-mean mm/day
    temperature_members = members_first(weekly, "t2m")  # degC
    u_mean = ensemble_mean(members_first(weekly, "u850"))
    v_mean = ensemble_mean(members_first(weekly, "v850"))
    fields = {
        "rainfall_total": embed(ensemble_mean(rain_members) * 7.0, rows, columns, shape),
        "temperature_mean": embed(ensemble_mean(temperature_members), rows, columns, shape),
        "rainfall_anomaly": embed(
            ensemble_mean(members_first(anomalies, "tp")), rows, columns, shape
        ),
        "temperature_anomaly": embed(
            ensemble_mean(members_first(anomalies, "t2m")), rows, columns, shape
        ),
        "wind850_mean": embed(wind_speed(u_mean, v_mean), rows, columns, shape),
    }
    vectors = {
        "u": embed(u_mean, rows, columns, shape),
        "v": embed(v_mean, rows, columns, shape),
    }
    products = product_definitions(template, members)

    weeks = []
    for index, (valid_start, valid_end) in enumerate(dates):
        weeks.append(
            {
                "week": index + 1,
                "valid_start": valid_start,
                "valid_end": valid_end,
                "fields": {key: flatten(fields[key][index]) for key in products},
                "summary": {
                    key: summary(fields[key][index], mask, latitude) for key in products
                },
                "vectors": {
                    "wind850_mean": {
                        "u": flatten(vectors["u"][index]),
                        "v": flatten(vectors["v"][index]),
                    }
                },
            }
        )

    model_state = initialization - timedelta(days=1)
    issue_path = f"forecasts/{args.source}/{args.issue}.json"
    speed = fields["wind850_mean"][:, coverage]
    return {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue": {
            "initialization": f"{initialization.isoformat()}T00:00:00Z",
            "information_cutoff": f"{initialization.isoformat()}T00:00:00Z",
            "model_state_time": f"{model_state.isoformat()}T00:00:00Z",
            "input_days": [
                (initialization - timedelta(days=2)).isoformat(),
                model_state.isoformat(),
            ],
            "input_source": (
                "ECMWF operational IFS Open Data 0.25-degree step-0 and 0-6 hour "
                f"fields for {(initialization - timedelta(days=2)).isoformat()} and "
                f"{model_state.isoformat()}; experimental IFS-initialized "
                "subseasonal model"
            ),
            "members": members,
            "lead_days": 42,
            "status": "warning",
            "scientific_status": (
                f"Limited {members}-member experimental IFS initialization, run "
                "retrospectively outside the operational pipeline. Anomalies use an "
                "ERA5 2011–2025 calendar-day climatology rather than lead-matched "
                "model reforecasts, so they include systematic model bias. Data "
                "cover 6–39°N, 66–99°E; wind anomalies, extremes and regional "
                "probabilities are withheld."
            ),
            "initial_condition_source": copy.deepcopy(SOURCE_BLOCKS[args.source]),
            "downloads": {"compact_json": f"data/{issue_path}"},
            "available_products": list(products),
            "capabilities": {
                "raw_fields": True,
                "anomalies": True,
                "regional_probabilities_eligible": False,
                "wind850_mean": True,
                "wind850_anomaly": False,
                "extreme_products": False,
                "joint_outcomes": False,
                "ensemble_spread": False,
            },
            "climatology_alignment": {
                "status": "era5_reference",
                "target_initialization_calendar_day": initialization.strftime("%m%d"),
                "operation_order": (
                    "subtract the ERA5 2011–2025 mean for each exact valid calendar "
                    "day from every member's daily field, then aggregate seven days "
                    "and average members"
                ),
                "message": (
                    "Observed-reanalysis baseline, not a model climatology; "
                    "anomalies include systematic model-versus-ERA5 bias."
                ),
            },
            "anomaly_baseline_note": (
                "Anomaly is the forecast minus the ERA5 reanalysis average for the "
                "same calendar days, 2011–2025. It is not a model climatology, so it "
                "also contains the model's systematic bias."
            ),
            "observation_verification": {
                "status": "not_available",
                "message": (
                    "Verification is withheld until every required observation day "
                    "in a valid week is available."
                ),
            },
        },
        "grid": {
            **{key: copy.deepcopy(value) for key, value in grid.items()},
            "coverage_mask": coverage.ravel().tolist(),
        },
        "products": products,
        "diagnostics": {
            "rainfall_weekly_mean_max_mm_day": float(
                forecast_spread(rain_members, member_axis=0).max()
            ),
            "temperature_weekly_mean_max_deg_c": float(
                forecast_spread(temperature_members, member_axis=0).max()
            ),
            "wind850_mean_speed_min_m_s": round(float(speed.min()), 4),
            "wind850_mean_speed_max_m_s": round(float(speed.max()), 4),
        },
        "weeks": weeks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly", type=Path, required=True)
    parser.add_argument("--anomaly", type=Path, required=True)
    parser.add_argument("--source", choices=tuple(SOURCE_BLOCKS), default="ifs")
    parser.add_argument("--issue", required=True, help="YYYYMMDD initialization")
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Published forecast JSON whose grid, India mask and legends are reused",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build(args)
    output = args.output or DATA / "forecasts" / args.source / f"{args.issue}.json"
    write_json(output, payload)
    print(f"wrote {output} ({payload['issue']['members']} members)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
