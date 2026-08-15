#!/usr/bin/env python3
"""Build matched ERA5/GFS/IFS initialization-sensitivity maps and metrics.

This is not a forecast-skill score. It isolates how the same FuXi-S2S model
changes when its initial-condition source changes. Skill requires observations
for the completed valid periods.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"
SOURCE_IDS = ("gfs", "era5", "ifs")
PAIR_IDS = (
    ("ifs", "era5"),
    ("gfs", "era5"),
    ("ifs", "gfs"),
)

from science.catalog import build_catalog  # noqa: E402
from science.validators import write_json as write_catalog_json  # noqa: E402

PRIVATE_OPERATIONAL_ROOT = Path(
    os.environ.get(
        "S2S_FUXI_STORAGE_ROOT",
        "/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/operational",
    )
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def private_forecast_path(public_forecast: dict[str, Any]) -> Path:
    source = public_forecast["issue"]["initial_condition_source"]["id"]
    issue = public_forecast["issue"]["initialization"][:10].replace("-", "")
    members = int(public_forecast["issue"]["members"])
    return (
        PRIVATE_OPERATIONAL_ROOT
        / source
        / issue
        / f"ens{members}"
        / "forecasts"
        / f"annual{issue[:4]}"
        / f"{issue}.nc"
    )


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    selected = np.isfinite(values) & (weights > 0)
    if not selected.any():
        raise ValueError("comparison has no supported finite values")
    return float(np.sum(values[selected] * weights[selected]) / np.sum(weights[selected]))


def weighted_pattern_correlation(
    left: np.ndarray, right: np.ndarray, weights: np.ndarray
) -> float:
    selected = np.isfinite(left) & np.isfinite(right) & (weights > 0)
    x = left[selected]
    y = right[selected]
    w = weights[selected]
    if x.size == 0:
        raise ValueError("comparison has no common finite values")
    w = w / w.sum()
    x = x - np.sum(w * x)
    y = y - np.sum(w * y)
    denominator = np.sqrt(np.sum(w * x * x) * np.sum(w * y * y))
    return float(np.sum(w * x * y) / denominator) if denominator > 0 else 0.0


def weekly_fields(path: Path) -> dict[str, Any]:
    with xr.open_dataset(path) as dataset:
        members = int(dataset.sizes.get("member", 0))
        leads = int(dataset.sizes.get("lead_day", 0))
        latitude_count = int(dataset.sizes.get("latitude", 0))
        longitude_count = int(dataset.sizes.get("longitude", 0))
        if members not in {5, 100}:
            raise ValueError(f"{path}: expected 5 or 100 members, found {members}")
        if leads != 42 or latitude_count < 1 or longitude_count < 1:
            raise ValueError(
                f"{path}: expected 42 leads and a non-empty grid; found "
                f"{leads}, {latitude_count}x{longitude_count}"
            )
        shape = (members, 6, 7, latitude_count, longitude_count)
        rain = dataset.tp.values.astype(np.float64).reshape(shape).mean(axis=2) * 24.0
        temperature = (
            dataset.t2m.values.astype(np.float64).reshape(shape).mean(axis=2) - 273.15
        )
        return {
            "rain_mean": rain.mean(axis=0),
            "temperature_mean": temperature.mean(axis=0),
            "rain_spread": rain.std(axis=0, ddof=0),
            "temperature_spread": temperature.std(axis=0, ddof=0),
            "latitude": dataset.latitude.values.astype(np.float64),
            "longitude": dataset.longitude.values.astype(np.float64),
            "valid_start": dataset.forecast_period_start.values[::7].astype("datetime64[D]"),
            "valid_end": dataset.forecast_period_end.values[6::7].astype("datetime64[D]")
            - np.timedelta64(1, "D"),
            "forecast_sha256": sha256(path),
            "members": members,
        }


def validate_matched(fields: dict[str, dict[str, Any]]) -> None:
    reference = fields[SOURCE_IDS[0]]
    for source in SOURCE_IDS[1:]:
        candidate = fields[source]
        if candidate["members"] != reference["members"]:
            raise ValueError("comparison sources have different ensemble sizes")
        for coordinate in ("latitude", "longitude", "valid_start", "valid_end"):
            if not np.array_equal(candidate[coordinate], reference[coordinate]):
                raise ValueError(f"comparison sources have different {coordinate} values")


def pair_metrics(
    left: dict[str, Any],
    right: dict[str, Any],
    variable: str,
    week: int,
    weights: np.ndarray,
) -> dict[str, Any]:
    mean_key = f"{variable}_mean"
    spread_key = f"{variable}_spread"
    difference = left[mean_key][week] - right[mean_key][week]
    return {
        "difference_field": np.round(difference.ravel(), 4).tolist(),
        "area_weighted_mean_difference": round(weighted_mean(difference, weights), 4),
        "mean_absolute_difference": round(
            weighted_mean(np.abs(difference), weights), 4
        ),
        "ensemble_mean_pattern_correlation": round(
            weighted_pattern_correlation(
                left[mean_key][week], right[mean_key][week], weights
            ),
            4,
        ),
        "left_mean_spread": round(weighted_mean(left[spread_key][week], weights), 4),
        "right_mean_spread": round(weighted_mean(right[spread_key][week], weights), 4),
    }


def build(
    date: str,
    forecast_paths: dict[str, Path] | None = None,
) -> Path:
    public_paths = {
        source: DATA / "forecasts" / source / f"{date}.json" for source in SOURCE_IDS
    }
    missing_public = [str(path) for path in public_paths.values() if not path.is_file()]
    if missing_public:
        raise FileNotFoundError(
            "three-source comparison requires every public forecast: "
            + ", ".join(missing_public)
        )
    public_forecasts = {
        source: json.loads(path.read_text(encoding="utf-8"))
        for source, path in public_paths.items()
    }
    issue_ids = {
        forecast["issue"]["initialization"][:10].replace("-", "")
        for forecast in public_forecasts.values()
    }
    members = {int(forecast["issue"]["members"]) for forecast in public_forecasts.values()}
    if issue_ids != {date} or len(members) != 1:
        raise ValueError("public forecasts are not identical-date, identical-member runs")
    private_paths = forecast_paths or {
        source: private_forecast_path(public_forecasts[source]) for source in SOURCE_IDS
    }
    fields = {source: weekly_fields(private_paths[source]) for source in SOURCE_IDS}
    validate_matched(fields)

    grid_shape = (len(fields["gfs"]["latitude"]), len(fields["gfs"]["longitude"]))
    mask_values = public_forecasts["gfs"]["grid"].get("india_mask")
    if not isinstance(mask_values, list) or len(mask_values) != np.prod(grid_shape):
        raise ValueError("GFS public forecast does not contain a matching India mask")
    mask = np.asarray(mask_values, dtype=bool).reshape(grid_shape)
    weights = np.cos(np.deg2rad(fields["gfs"]["latitude"]))[:, None] * mask

    pairs: list[dict[str, Any]] = []
    for left_id, right_id in PAIR_IDS:
        weeks = []
        for week in range(6):
            weeks.append(
                {
                    "week": week + 1,
                    "valid_start": str(fields[left_id]["valid_start"][week]),
                    "valid_end": str(fields[left_id]["valid_end"][week]),
                    "rainfall": pair_metrics(
                        fields[left_id], fields[right_id], "rain", week, weights
                    ),
                    "temperature": pair_metrics(
                        fields[left_id], fields[right_id], "temperature", week, weights
                    ),
                }
            )
        pairs.append(
            {
                "id": f"{left_id}_minus_{right_id}",
                "left_source_id": left_id,
                "right_source_id": right_id,
                "label": f"{left_id.upper()} − {right_id.upper()}",
                "weeks": weeks,
            }
        )

    output = DATA / "comparisons" / f"{date}.json"
    interpretation = (
        "Pairwise differences measure sensitivity to the initial-condition source. "
        "They do not show which forecast is better; skill requires observations "
        "for each complete valid period."
    )
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue_date": f"{date[:4]}-{date[4:6]}-{date[6:]}T00:00:00Z",
        "comparison_type": "matched_initialization_source_sensitivity",
        "skill_status": "not_yet_verifiable",
        "interpretation": interpretation,
        "grid": {
            "shape": list(grid_shape),
            "latitude": fields["gfs"]["latitude"].tolist(),
            "longitude": fields["gfs"]["longitude"].tolist(),
            "value_order": "latitude-major row order",
        },
        "sources": {
            source: {
                "members": fields[source]["members"],
                "forecast_sha256": fields[source]["forecast_sha256"],
                "public_forecast": public_paths[source].relative_to(DATA).as_posix(),
            }
            for source in SOURCE_IDS
        },
        "pairs": pairs,
    }
    write_json(output, payload)
    for source, forecast_path in public_paths.items():
        forecast = public_forecasts[source]
        forecast["issue"]["initialization_comparison"] = {
            "status": "initialization_sensitivity_only",
            "compared_source_ids": list(SOURCE_IDS),
            "comparison": output.relative_to(DATA).as_posix(),
            "message": interpretation,
        }
        write_json(forecast_path, forecast)
    index_path = DATA / "index.json"
    write_catalog_json(
        index_path,
        build_catalog(
            json.loads(index_path.read_text(encoding="utf-8")),
            PUBLIC,
            datetime.now(timezone.utc),
        ),
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Issue date YYYYMMDD")
    for source in SOURCE_IDS:
        parser.add_argument(f"--{source}-forecast", type=Path)
    args = parser.parse_args()
    if len(args.date) != 8 or not args.date.isdigit():
        raise SystemExit("date must use YYYYMMDD")
    overrides = {
        source: getattr(args, f"{source}_forecast") for source in SOURCE_IDS
    }
    paths = None if not any(overrides.values()) else {
        source: overrides[source] or private_forecast_path(
            json.loads(
                (DATA / "forecasts" / source / f"{args.date}.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        for source in SOURCE_IDS
    }
    print(build(args.date, paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
