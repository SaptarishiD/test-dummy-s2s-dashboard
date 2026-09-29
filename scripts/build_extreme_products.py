#!/usr/bin/env python3
"""Build compact EFI/SOT fields and paired regional outcome matrices."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from science.extremes import (  # noqa: E402
    PUBLIC_PERCENTILE_LEVELS,
    complete_weekly_samples,
    extreme_forecast_index,
    paired_tercile_matrix,
    quantiles,
    shift_of_tails,
)
from science.zarr_v2 import read_array, read_attrs  # noqa: E402
from scripts.build_regional_outlook import (  # noqa: E402
    REGION_ORDER,
    area_weights,
    load_json,
    region_geometries,
    regional_land_fractions,
    spatial_mean,
)


SUPPORTED_ISSUE = "20260926"
CLIMATE_YEARS = tuple(range(2002, 2022))
CLIMATE_SLOTS = ("0922", "0926", "0929")
INDO_GANGETIC_PROXY_ID = "indo_gangetic_administrative_proxy"
INDO_GANGETIC_PROXY_LABEL = "Indo-Gangetic administrative proxy"
INDO_GANGETIC_STATES = (
    "PUNJAB",
    "HARYANA",
    "DELHI",
    "UTTAR PRADESH",
    "BIHAR",
    "WEST BENGAL",
)

EFI_PRODUCT = {
    "label": "Extreme Forecast Index",
    "short_label": "EFI",
    "description": "Tail-weighted difference between the raw forecast-member and matched model-climate CDFs",
    "units": "index",
    "baseline": "FuXi native reforecasts, 2002–2021 · three initialization dates",
    "legend": {
        "boundaries": [-1.0, -0.8, -0.5, 0.0, 0.5, 0.8, 1.0],
        "colors": ["#243b75", "#6f93bd", "#d9e6ef", "#f4dfc7", "#df8055", "#8e2c2a"],
        "under": "#172754",
        "over": "#681b20",
    },
}

SOT_PRODUCT = {
    "label": "Shift of Tails",
    "short_label": "SOT",
    "description": "Forecast-tail displacement relative to the matched model-climate 90–99% or 10–1% tail width",
    "units": "index",
    "baseline": "FuXi native reforecasts, 2002–2021 · three initialization dates",
    "legend": {
        "boundaries": [-1.0, 0.0, 0.5, 1.0, 2.0],
        "colors": ["#cbd5e1", "#f5f3eb", "#f4c97a", "#e7893d"],
        "under": "#334155",
        "over": "#6f1d27",
        "bin_labels": ["<−1", "−1–0", "0–0.5", "0.5–1", "1–2", ">2"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--public-forecast", type=Path, required=True)
    parser.add_argument("--regional", type=Path, required=True)
    parser.add_argument(
        "--reforecast-zarr",
        type=Path,
        default=Path(
            "/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/"
            "native_reforecast_global_2002_2021.zarr"
        ),
    )
    parser.add_argument(
        "--reforecast-shards",
        type=Path,
        default=Path(
            "/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi/"
            "native_reforecast_jjas_2002_2021/shards"
        ),
        help="Lossless India subsets used to avoid a full global chunk scan.",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=ROOT / ".private-cache/fuxi-mclimate-0922-0926-0929.npz",
    )
    parser.add_argument(
        "--india-admin",
        type=Path,
        default=ROOT / "public/data/india-admin.json",
    )
    parser.add_argument("--catalog", type=Path, default=ROOT / "public/data/index.json")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def finite_or_none(values: np.ndarray, digits: int = 4) -> list[float | None]:
    flattened = np.asarray(values, dtype=np.float64).ravel()
    return [round(float(value), digits) if np.isfinite(value) else None for value in flattened]


def climate_reference(zarr_path: Path) -> tuple[str, dict[str, Any]]:
    attrs = read_attrs(zarr_path)
    if attrs.get("status") != "complete":
        raise ValueError("native global reforecast archive is not marked complete")
    years = str(attrs.get("source_years"))
    members = int(attrs.get("source_member_count", -1))
    leads = int(attrs.get("source_lead_count", -1))
    if years != "2002-2021" or members != 51 or leads != 42:
        raise ValueError("native global reforecast archive contract does not match")
    dates = {str(value) for value in read_array(zarr_path, "init_yyyymmdd")}
    expected_dates = {f"{year}{slot}" for year in CLIMATE_YEARS for slot in CLIMATE_SLOTS}
    if not expected_dates.issubset(dates):
        raise ValueError("native global archive lacks one or more selected initialization dates")
    archive_hash = str(attrs["archive_records_sha256"])
    reference_id = (
        "fuxi-mclim-2002_2021-slots0922_0926_0929-leads01_42-"
        f"n3060-tp_sum7d-t2m_mean7d-qlinear-src{archive_hash[:12]}"
    )
    return reference_id, attrs


def build_cache(args: argparse.Namespace) -> dict[str, Any]:
    reference_id, archive_attrs = climate_reference(args.reforecast_zarr)
    if args.cache.exists():
        cached = np.load(args.cache, allow_pickle=False)
        cached_reference = str(cached["reference_id"].item())
        if cached_reference != reference_id:
            raise ValueError("private model-climate cache reference does not match archive")
        return {
            "reference_id": reference_id,
            "rainfall": cached["rainfall"],
            "temperature": cached["temperature"],
            "latitude": cached["latitude"],
            "longitude": cached["longitude"],
            "archive_attrs": archive_attrs,
        }

    rainfall: list[np.ndarray] = []
    temperature: list[np.ndarray] = []
    latitude: np.ndarray | None = None
    longitude: np.ndarray | None = None
    for year in CLIMATE_YEARS:
        for slot in CLIMATE_SLOTS:
            path = args.reforecast_shards / f"{year}{slot}.nc"
            with xr.open_dataset(path) as dataset:
                required = {"member": 51, "lead_day": 42, "latitude": 27, "longitude": 27}
                if any(int(dataset.sizes.get(key, -1)) != size for key, size in required.items()):
                    raise ValueError(f"reforecast shard has incomplete dimensions: {path}")
                if dataset.tp.attrs.get("units") != "mm h-1" or dataset.t2m.attrs.get("units") != "K":
                    raise ValueError(f"reforecast shard units are unexpected: {path}")
                shard_latitude = dataset.latitude.values.astype(np.float64)
                shard_longitude = dataset.longitude.values.astype(np.float64)
                if latitude is None:
                    latitude, longitude = shard_latitude, shard_longitude
                else:
                    np.testing.assert_array_equal(latitude, shard_latitude)
                    np.testing.assert_array_equal(longitude, shard_longitude)
                rain_daily = dataset.tp.transpose(
                    "member", "lead_day", "latitude", "longitude"
                ).values.astype(np.float64) * 24.0
                temperature_daily = dataset.t2m.transpose(
                    "member", "lead_day", "latitude", "longitude"
                ).values.astype(np.float64) - 273.15
                rain_weekly = complete_weekly_samples(rain_daily, aggregation="sum")
                temperature_weekly = complete_weekly_samples(
                    temperature_daily, aggregation="mean"
                )
                if not np.all(np.isfinite(rain_weekly)) or not np.all(
                    np.isfinite(temperature_weekly)
                ):
                    raise ValueError(f"reforecast shard has an incomplete member-week: {path}")
                rainfall.append(rain_weekly.astype(np.float32))
                temperature.append(temperature_weekly.astype(np.float32))

    cache_rainfall = np.concatenate(rainfall, axis=0)
    cache_temperature = np.concatenate(temperature, axis=0)
    if cache_rainfall.shape != (3060, 6, 27, 27):
        raise ValueError(f"unexpected model-climate shape: {cache_rainfall.shape}")
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.cache,
        reference_id=np.asarray(reference_id),
        rainfall=cache_rainfall,
        temperature=cache_temperature,
        latitude=latitude,
        longitude=longitude,
    )
    return {
        "reference_id": reference_id,
        "rainfall": cache_rainfall,
        "temperature": cache_temperature,
        "latitude": latitude,
        "longitude": longitude,
        "archive_attrs": archive_attrs,
    }


def load_forecast(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    with xr.open_dataset(path) as dataset:
        required = {"member": 100, "lead_day": 42, "latitude": 27, "longitude": 27}
        if any(int(dataset.sizes.get(key, -1)) != size for key, size in required.items()):
            raise ValueError("extreme products require a complete 100-member 42-day forecast")
        rainfall = complete_weekly_samples(
            dataset.tp.transpose("member", "lead_day", "latitude", "longitude")
            .values.astype(np.float64)
            * 24.0,
            aggregation="sum",
        )
        temperature = complete_weekly_samples(
            dataset.t2m.transpose("member", "lead_day", "latitude", "longitude")
            .values.astype(np.float64)
            - 273.15,
            aggregation="mean",
        )
        return (
            rainfall,
            temperature,
            dataset.latitude.values.astype(np.float64),
            dataset.longitude.values.astype(np.float64),
        )


def distribution_summary(forecast: np.ndarray, climate: np.ndarray) -> dict[str, Any]:
    forecast_quantiles = quantiles(forecast, PUBLIC_PERCENTILE_LEVELS)
    climate_quantiles = quantiles(climate, PUBLIC_PERCENTILE_LEVELS)
    return {
        "probabilities": [round(float(value), 2) for value in PUBLIC_PERCENTILE_LEVELS],
        "forecast": [finite_or_none(values, 3) for values in forecast_quantiles],
        "climate": [finite_or_none(values, 3) for values in climate_quantiles],
    }


def field_summary(values: np.ndarray, support_mask: np.ndarray) -> dict[str, float]:
    finite = np.isfinite(values)
    supported = finite & support_mask
    selected = values[supported] if np.any(supported) else values[finite]
    return {
        "india_weighted_mean": round(float(np.mean(selected)), 3),
        "india_minimum": round(float(np.min(selected)), 3),
        "india_maximum": round(float(np.max(selected)), 3),
    }


def add_forecast_products(
    payload: dict[str, Any],
    rainfall: np.ndarray,
    temperature: np.ndarray,
    climate: dict[str, Any],
    forecast_sha: str,
) -> None:
    climate_rainfall = np.asarray(climate["rainfall"])
    climate_temperature = np.asarray(climate["temperature"])
    payload["schema_version"] = 3
    payload["extreme_definition"] = {
        "status": "model_relative_raw_ensemble_indices",
        "reference_id": climate["reference_id"],
        "years": list(CLIMATE_YEARS),
        "initialization_dates": list(CLIMATE_SLOTS),
        "lead_days": [1, 42],
        "forecast_member_count": 100,
        "climate_sample_count": 3060,
        "source_archive": "native_reforecast_global_2002_2021.zarr",
        "source_archive_records_sha256": climate["archive_attrs"]["archive_records_sha256"],
        "forecast_sha256": forecast_sha,
        "aggregation": {"rainfall": "7-day total in mm/week", "temperature": "7-day mean in deg C"},
        "quantile_method": "NumPy linear quantiles",
        "efi": "ECMWF tail-weighted CDF index; bounded to -1…+1 after numerical integration",
        "sot_upper": "(forecast q90 - climate q99) / (climate q99 - climate q90)",
        "sot_lower": "(forecast q10 - climate q01) / (climate q01 - climate q10); temperature only",
        "warning": "EFI and SOT are raw model-relative ensemble indices, not probabilities, warnings, calibration, skill, guaranteed impacts, or evidence of forecast accuracy.",
    }
    payload["products"].update(
        {
            "rainfall_efi": {**EFI_PRODUCT, "label": "Rainfall Extreme Forecast Index"},
            "temperature_efi": {**EFI_PRODUCT, "label": "Temperature Extreme Forecast Index"},
            "rainfall_sot_upper": {**SOT_PRODUCT, "label": "Rainfall upper-tail Shift of Tails"},
            "temperature_sot_upper": {**SOT_PRODUCT, "label": "Temperature upper-tail Shift of Tails"},
            "temperature_sot_lower": {**SOT_PRODUCT, "label": "Temperature lower-tail Shift of Tails"},
            "rainfall_spread": {
                "label": "Rainfall ensemble spread",
                "short_label": "Rainfall spread",
                "description": "Population standard deviation across weekly-total forecast members",
                "units": "mm week⁻¹",
                "baseline": None,
                "legend": {"boundaries": [0, 5, 10, 20, 40, 70, 110], "colors": ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#4292c6", "#08519c"], "under": "#ffffff", "over": "#08306b"},
            },
            "temperature_spread": {
                "label": "Temperature ensemble spread",
                "short_label": "Temperature spread",
                "description": "Population standard deviation across weekly-mean forecast members",
                "units": "°C",
                "baseline": None,
                "legend": {"boundaries": [0, 0.5, 1, 1.5, 2, 3, 5], "colors": ["#fff7ec", "#fee8c8", "#fdd49e", "#fdbb84", "#e34a33", "#b30000"], "under": "#ffffff", "over": "#7f0000"},
            },
        }
    )
    extreme_keys = [
        "rainfall_spread", "temperature_spread", "rainfall_efi", "temperature_efi",
        "rainfall_sot_upper", "temperature_sot_upper", "temperature_sot_lower",
    ]
    available = payload["issue"].setdefault("available_products", [])
    for key in extreme_keys:
        if key not in available:
            available.append(key)
    payload["issue"].setdefault("capabilities", {}).update(
        {"extreme_products": True, "joint_outcomes": True, "ensemble_spread": True}
    )

    for week_index, week in enumerate(payload["weeks"]):
        rain_forecast = rainfall[:, week_index]
        temp_forecast = temperature[:, week_index]
        rain_climate = climate_rainfall[:, week_index]
        temp_climate = climate_temperature[:, week_index]
        derived = {
            "rainfall_spread": np.nanstd(rain_forecast, axis=0),
            "temperature_spread": np.nanstd(temp_forecast, axis=0),
            "rainfall_efi": extreme_forecast_index(rain_forecast, rain_climate),
            "temperature_efi": extreme_forecast_index(temp_forecast, temp_climate),
            "rainfall_sot_upper": shift_of_tails(rain_forecast, rain_climate, tail="upper"),
            "temperature_sot_upper": shift_of_tails(temp_forecast, temp_climate, tail="upper"),
            "temperature_sot_lower": shift_of_tails(temp_forecast, temp_climate, tail="lower"),
        }
        week["fields"].update(
            {key: finite_or_none(values, 3 if key.endswith("spread") else 4) for key, values in derived.items()}
        )
        support_mask = np.asarray(payload["grid"].get("india_mask", np.ones((27, 27))), dtype=bool).reshape(27, 27)
        week["summary"].update(
            {key: field_summary(values, support_mask) for key, values in derived.items()}
        )
        week["extreme_samples"] = {
            "forecast_valid_member_count": np.sum(np.isfinite(rain_forecast) & np.isfinite(temp_forecast), axis=0).astype(int).ravel().tolist(),
            "climate_valid_sample_count": np.sum(np.isfinite(rain_climate) & np.isfinite(temp_climate), axis=0).astype(int).ravel().tolist(),
        }
        week["distribution_summaries"] = {
            "rainfall": distribution_summary(rain_forecast, rain_climate),
            "temperature": distribution_summary(temp_forecast, temp_climate),
        }


def proxy_geometry(admin: dict[str, Any]) -> Any:
    from shapely import make_valid
    from shapely.geometry import shape
    from shapely.ops import unary_union

    features = {
        feature["properties"]["name"]: make_valid(shape(feature["geometry"]))
        for feature in admin["features"]
    }
    missing = set(INDO_GANGETIC_STATES) - features.keys()
    if missing:
        raise ValueError(f"India geometry lacks proxy states: {sorted(missing)}")
    return make_valid(unary_union([features[name] for name in INDO_GANGETIC_STATES]))


def add_regional_products(
    payload: dict[str, Any],
    public_forecast: dict[str, Any],
    rainfall: np.ndarray,
    temperature: np.ndarray,
    climate: dict[str, Any],
    admin_path: Path,
) -> None:
    admin = load_json(admin_path)
    geometries, _ = region_geometries(admin)
    geometries[INDO_GANGETIC_PROXY_ID] = proxy_geometry(admin)
    latitude = np.asarray(climate["latitude"], dtype=np.float64)
    longitude = np.asarray(climate["longitude"], dtype=np.float64)
    spacing = float(public_forecast["grid"]["spacing_degrees"])
    region_ids = (*REGION_ORDER, INDO_GANGETIC_PROXY_ID)
    fractions = {
        region_id: regional_land_fractions(
            geometries[region_id], latitude, longitude, spacing
        )
        for region_id in region_ids
    }
    weights = {
        region_id: area_weights(latitude, fractions[region_id])
        for region_id in region_ids
    }
    payload["schema_version"] = 3
    payload["extreme_definition"] = public_forecast["extreme_definition"]
    definitions = payload["region_definition"]["regions"]
    if not any(region["id"] == INDO_GANGETIC_PROXY_ID for region in definitions):
        definitions.append(
            {
                "id": INDO_GANGETIC_PROXY_ID,
                "label": INDO_GANGETIC_PROXY_LABEL,
                "short_label": "Indo-Gangetic proxy",
                "states_and_union_territories": list(INDO_GANGETIC_STATES),
                "equivalent_native_grid_cells": round(float(fractions[INDO_GANGETIC_PROXY_ID].sum()), 2),
            }
        )
    payload["joint_outcome_definition"] = {
        "label": "Joint raw member fractions",
        "rainfall_categories": ["below_normal", "near_normal", "above_normal"],
        "temperature_categories": ["cooler", "near_normal", "warmer"],
        "aggregation": "Paired rainfall and temperature values from the same member after cos(latitude) × regional land-fraction aggregation.",
        "boundary_rule": "Values equal to either tercile threshold are assigned to near normal.",
        "warning": "Cells are paired raw-member fractions. Marginal probabilities are not multiplied and independence is not assumed.",
    }
    climate_rainfall = np.asarray(climate["rainfall"])
    climate_temperature = np.asarray(climate["temperature"])
    for week_index, week in enumerate(payload["weeks"]):
        records = {record["id"]: record for record in week["regions"]}
        for region_id in region_ids:
            rain_forecast = spatial_mean(rainfall[:, week_index], weights[region_id])
            temp_forecast = spatial_mean(temperature[:, week_index], weights[region_id])
            rain_climate = spatial_mean(climate_rainfall[:, week_index], weights[region_id])
            temp_climate = spatial_mean(climate_temperature[:, week_index], weights[region_id])
            rain_thresholds = tuple(np.quantile(rain_climate, [1 / 3, 2 / 3], method="linear"))
            temp_thresholds = tuple(np.quantile(temp_climate, [1 / 3, 2 / 3], method="linear"))
            matrix = paired_tercile_matrix(
                rain_forecast, temp_forecast, rain_thresholds, temp_thresholds
            )
            joint = {
                "paired_member_count": matrix["paired_member_count"],
                "counts": np.asarray(matrix["counts"]).astype(int).tolist(),
                "percentages": np.round(np.asarray(matrix["percentages"]), 6).tolist(),
                "rainfall_terciles_mm_week": [round(float(value), 3) for value in rain_thresholds],
                "temperature_terciles_deg_c": [round(float(value), 3) for value in temp_thresholds],
            }
            if region_id in records:
                records[region_id]["joint_tercile"] = joint
            else:
                week["regions"].append(
                    {
                        "id": region_id,
                        "label": INDO_GANGETIC_PROXY_LABEL,
                        "short_label": "Indo-Gangetic proxy",
                        "rainfall": {},
                        "temperature": {},
                        "joint_tercile": joint,
                    }
                )


def update_catalog(path: Path, forecast_path: Path, regional_path: Path) -> None:
    catalog = load_json(path)
    source = next(item for item in catalog["initial_condition_sources"] if item["id"] == "ifs")
    issue = next(item for item in source["issues"] if item["id"] == SUPPORTED_ISSUE)
    public = load_json(forecast_path)
    available = public["issue"].get("available_products", list(public["products"]))
    issue["available_products"] = available
    issue.setdefault("capabilities", {}).update(
        {
            "extreme_products": True,
            "joint_outcomes": True,
            "ensemble_spread": True,
            "regional_probabilities": True,
        }
    )
    issue.setdefault("checksums", {}).update(
        {
            "forecast_sha256": sha256(forecast_path),
            "regional_sha256": sha256(regional_path),
        }
    )
    # Preserve the operational current/default pointers. IFS 20260927 remains
    # the newest published forecast, while 20260926 is the newest issue whose
    # native model-climate window meets this product's three-start contract.
    write_json(path, catalog)


def build(args: argparse.Namespace) -> None:
    public_forecast = load_json(args.public_forecast)
    issue_id = public_forecast["issue"]["initialization"][:10].replace("-", "")
    source_id = public_forecast["issue"]["initial_condition_source"]["id"]
    if issue_id != SUPPORTED_ISSUE or source_id != "ifs":
        raise ValueError(f"extreme products are initially supported only for IFS {SUPPORTED_ISSUE}")
    climate = build_cache(args)
    rainfall, temperature, latitude, longitude = load_forecast(args.forecast)
    np.testing.assert_array_equal(latitude, climate["latitude"])
    np.testing.assert_array_equal(longitude, climate["longitude"])
    np.testing.assert_array_equal(latitude, np.asarray(public_forecast["grid"]["latitude"]))
    np.testing.assert_array_equal(longitude, np.asarray(public_forecast["grid"]["longitude"]))
    add_forecast_products(
        public_forecast, rainfall, temperature, climate, sha256(args.forecast)
    )
    write_json(args.public_forecast, public_forecast)

    regional = load_json(args.regional)
    add_regional_products(
        regional, public_forecast, rainfall, temperature, climate, args.india_admin
    )
    write_json(args.regional, regional)
    update_catalog(args.catalog, args.public_forecast, args.regional)
    print(
        f"wrote EFI/SOT and joint outcomes for IFS {SUPPORTED_ISSUE}; "
        f"reference={climate['reference_id']}"
    )


def main() -> int:
    build(parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
