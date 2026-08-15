#!/usr/bin/env python3
"""Export one configured FuXi bounding-box forecast, geography, catalog, and PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"
SPACING = 1.5
MAP_WIDTH = 620.0
SOURCE_DEFINITIONS = {
    "gfs": {
        "label": "GFS operational proxy",
        "short_label": "GFS",
        "category": "operational_proxy",
        "availability": "near_real_time",
    },
    "ifs": {
        "label": "IFS operational initialization",
        "short_label": "IFS",
        "category": "operational_initialization",
        "availability": "near_real_time",
    },
    "era5": {
        "label": "ERA5 reanalysis reference",
        "short_label": "ERA5",
        "category": "reanalysis_reference",
        "availability": "delayed_reference",
    },
}
PRODUCTS = {
    "rainfall_total": {
        "label": "Rainfall weekly total",
        "short_label": "Rainfall",
        "description": "Ensemble-mean seven-day accumulation",
        "units": "mm / 7 days",
        "baseline": None,
        "colors": "Blues",
    },
    "temperature_mean": {
        "label": "Weekly mean 2 m temperature",
        "short_label": "Temperature",
        "description": "Ensemble-mean seven-day mean",
        "units": "°C",
        "baseline": None,
        "colors": "turbo",
    },
}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    domain_id = str(config.get("id", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", domain_id) or domain_id == "india":
        raise ValueError("domain id must be a non-India lowercase slug")
    label = str(config.get("label", "")).strip()
    if not label:
        raise ValueError("domain label is required")
    bounds = config.get("bounds", {})
    try:
        north, south, west, east = (
            float(bounds[key]) for key in ("north", "south", "west", "east")
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("bounds require numeric north/south/west/east") from exc
    if not (-90 <= south < north <= 90):
        raise ValueError("domain latitude bounds are inverted or outside -90..90")
    if not (-180 <= west < east <= 358.5):
        raise ValueError("domain longitude bounds are inverted, out of range, or cross the antimeridian")
    for name, value in (("north", north), ("south", south), ("west", west), ("east", east)):
        if not np.isclose(value / SPACING, round(value / SPACING), atol=1e-8):
            raise ValueError(f"{name}={value} is not aligned to the 1.5-degree FuXi grid")
    products = config.get("products", ["rainfall_total", "temperature_mean"])
    if products != ["rainfall_total", "temperature_mean"]:
        raise ValueError("custom-domain v1 supports rainfall_total and temperature_mean")
    return {
        "id": domain_id,
        "label": label,
        "kind": "configured_bbox",
        "bounds": {"north": north, "south": south, "west": west, "east": east},
        "products": products,
        "pdf": bool(config.get("pdf", True)),
    }


def _rings(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon


def build_geography(domain: dict[str, Any]) -> tuple[dict[str, Any], list[np.ndarray]]:
    world_path = DATA / "world-countries.geojson"
    world = read_json(world_path)
    bounds = domain["bounds"]
    west, east = bounds["west"] - SPACING / 2, bounds["east"] + SPACING / 2
    south, north = bounds["south"] - SPACING / 2, bounds["north"] + SPACING / 2
    height = max(260.0, min(760.0, round(MAP_WIDTH * (north - south) / (east - west))))

    def project(longitude: float, latitude: float) -> tuple[float, float]:
        return (
            (longitude - west) / (east - west) * MAP_WIDTH,
            (north - latitude) / (north - south) * height,
        )

    paths: list[str] = []
    segments: list[np.ndarray] = []
    for feature in world.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        for ring in _rings(geometry):
            array = np.asarray(ring, dtype=float)
            if array.size == 0:
                continue
            if (
                array[:, 0].max() < west
                or array[:, 0].min() > east
                or array[:, 1].max() < south
                or array[:, 1].min() > north
            ):
                continue
            segments.append(array[:, :2])
            points = [project(float(lon), float(lat)) for lon, lat, *_ in ring]
            if len(points) >= 3:
                paths.append(
                    "M"
                    + "L".join(f"{x:.1f},{y:.1f}" for x, y in points)
                    + "Z"
                )
    payload = {
        "schema_version": 1,
        "description": f"Pre-projected Natural Earth boundaries for {domain['label']}",
        "view_box": [0, 0, int(MAP_WIDTH), int(height)],
        "world_path": "".join(paths),
        "india_outline_path": "",
        "india_admin_path": "",
        "sources": {
            "world_countries_sha256": sha256(world_path),
            "india_outline_sha256": "not_applicable",
            "india_admin_sha256": "not_applicable",
        },
    }
    if not payload["world_path"]:
        raise ValueError("configured domain contains no Natural Earth boundary geometry")
    return payload, segments


def field_summary(values: np.ndarray, latitude: np.ndarray) -> dict[str, float]:
    weights = np.broadcast_to(np.cos(np.deg2rad(latitude))[:, None], values.shape)
    selected = np.isfinite(values)
    return {
        "area_weighted_mean": round(
            float(np.sum(values[selected] * weights[selected]) / np.sum(weights[selected])),
            4,
        ),
        "minimum": round(float(np.nanmin(values)), 4),
        "maximum": round(float(np.nanmax(values)), 4),
    }


def forecast_payload(
    forecast_path: Path,
    source_id: str,
    domain: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    with xr.open_dataset(forecast_path) as dataset:
        latitude = dataset.latitude.values.astype(float)
        longitude = dataset.longitude.values.astype(float)
        bounds = domain["bounds"]
        expected_latitude = np.arange(bounds["north"], bounds["south"] - 0.01, -SPACING)
        expected_longitude = np.arange(bounds["west"], bounds["east"] + 0.01, SPACING)
        if not np.allclose(latitude, expected_latitude) or not np.allclose(
            longitude, expected_longitude
        ):
            raise ValueError(
                "forecast grid does not exactly match the configured domain; "
                "rerun FuXi with the same center-coordinate bounds"
            )
        members = int(dataset.sizes.get("member", 0))
        if members not in {5, 100} or dataset.sizes.get("lead_day") != 42:
            raise ValueError("domain export requires a complete 5- or 100-member, 42-day run")
        shape = (members, 6, 7, len(latitude), len(longitude))
        rain = dataset.tp.values.astype(float).reshape(shape).mean(axis=0).sum(axis=1) * 24.0
        temperature = (
            dataset.t2m.values.astype(float).reshape(shape).mean(axis=0).mean(axis=1)
            - 273.15
        )
        initialization_day = dataset.forecast_reference_time.values.astype("datetime64[D]")
        model_state_day = dataset.model_state_time.values.astype("datetime64[D]")
        issue_id = np.datetime_as_string(initialization_day, unit="D").replace("-", "")
        starts = dataset.forecast_period_start.values[::7].astype("datetime64[D]")
        ends = dataset.forecast_period_end.values[6::7].astype("datetime64[D]") - np.timedelta64(1, "D")
        input_source = str(dataset.attrs.get("input_source", source_id.upper()))

    definition = SOURCE_DEFINITIONS[source_id]
    weeks = []
    for index in range(6):
        fields = {
            "rainfall_total": np.round(rain[index].ravel(), 4).tolist(),
            "temperature_mean": np.round(temperature[index].ravel(), 4).tolist(),
        }
        weeks.append(
            {
                "week": index + 1,
                "valid_start": str(starts[index]),
                "valid_end": str(ends[index]),
                "fields": fields,
                "summary": {
                    "rainfall_total": field_summary(rain[index], latitude),
                    "temperature_mean": field_summary(temperature[index], latitude),
                },
            }
        )
    relative = Path("domains") / domain["id"] / "forecasts" / source_id / f"{issue_id}.json"
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": {key: domain[key] for key in ("id", "label", "kind", "bounds")},
        "issue": {
            "initialization": str(initialization_day) + "T00:00:00Z",
            "information_cutoff": str(initialization_day) + "T00:00:00Z",
            "model_state_time": str(model_state_day) + "T00:00:00Z",
            "input_days": [
                str(model_state_day - np.timedelta64(1, "D")),
                str(model_state_day),
            ],
            "input_source": input_source,
            "members": members,
            "lead_days": 42,
            "status": "warning",
            "scientific_status": "Experimental raw configured-domain guidance",
            "initial_condition_source": {
                "id": source_id,
                **definition,
                "description": "Configured-domain raw forecast export",
            },
            "available_products": domain["products"],
            "capabilities": {
                "raw_fields": True,
                "anomalies": False,
                "regional_probabilities_eligible": False,
                "pdf": domain["pdf"],
            },
            "downloads": {"compact_json": f"data/{relative.as_posix()}"},
            "observation_verification": {
                "status": "not_available",
                "message": "Custom-domain verification is not available in v1.",
            },
        },
        "grid": {
            "shape": [len(latitude), len(longitude)],
            "spacing_degrees": SPACING,
            "latitude": latitude.tolist(),
            "longitude": longitude.tolist(),
            "support_mask": [True] * (len(latitude) * len(longitude)),
            "supported_cell_count": len(latitude) * len(longitude),
            "value_order": "latitude-major row order; latitude is north-to-south",
        },
        "products": {
            key: {field: value for field, value in PRODUCTS[key].items() if field != "colors"}
            | {
                "legend": {
                    "boundaries": [0, 10, 25, 50, 100, 150, 250, 400]
                    if key == "rainfall_total"
                    else [-20, -10, 0, 10, 20, 30, 40, 50],
                    "colors": ["#f7fbff", "#deebf7", "#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"]
                    if key == "rainfall_total"
                    else ["#313695", "#74add1", "#e0f3f8", "#ffffbf", "#fdae61", "#f46d43", "#a50026"],
                    "under": "#ffffff" if key == "rainfall_total" else "#22225f",
                    "over": "#041f4a" if key == "rainfall_total" else "#6a0016",
                }
            }
            for key in domain["products"]
        },
        "diagnostics": {
            "rainfall_weekly_mean_max_mm_day": round(float(np.nanmax(rain / 7.0)), 4),
            "temperature_weekly_mean_max_deg_c": round(float(np.nanmax(temperature)), 4),
        },
        "weeks": weeks,
    }
    return payload, issue_id


def build_pdf(
    payload: dict[str, Any],
    source_id: str,
    issue_id: str,
    domain: dict[str, Any],
    segments: list[np.ndarray],
) -> Path:
    output = PUBLIC / "downloads" / "domains" / domain["id"] / source_id / issue_id
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"S2S_Research_{domain['id']}_Weeks1-4_{source_id.upper()}_{issue_id}.pdf"
    bounds = domain["bounds"]
    with PdfPages(path) as pdf:
        for product_key in domain["products"]:
            figure, axes_grid = plt.subplots(2, 2, figsize=(11.7, 11.7), constrained_layout=True)
            figure.suptitle(
                f"{domain['label']} · {PRODUCTS[product_key]['label']} · {source_id.upper()} · {issue_id}",
                fontsize=16,
            )
            image = None
            for axes, week in zip(axes_grid.flat, payload["weeks"][:4], strict=True):
                values = np.asarray(week["fields"][product_key]).reshape(payload["grid"]["shape"])
                if product_key == "rainfall_total":
                    values = values / 7.0
                image = axes.imshow(
                    values,
                    extent=(
                        bounds["west"] - SPACING / 2,
                        bounds["east"] + SPACING / 2,
                        bounds["south"] - SPACING / 2,
                        bounds["north"] + SPACING / 2,
                    ),
                    origin="upper",
                    cmap=PRODUCTS[product_key]["colors"],
                    aspect="auto",
                )
                for segment in segments:
                    axes.plot(segment[:, 0], segment[:, 1], color="#333333", linewidth=0.45)
                axes.set_xlim(bounds["west"] - SPACING / 2, bounds["east"] + SPACING / 2)
                axes.set_ylim(bounds["south"] - SPACING / 2, bounds["north"] + SPACING / 2)
                axes.set_title(f"Week {week['week']} · {week['valid_start']} – {week['valid_end']}")
                axes.grid(alpha=0.2, linestyle=":")
            figure.colorbar(image, ax=axes_grid.ravel().tolist(), shrink=0.7)
            figure.text(
                0.5,
                0.01,
                "Experimental raw configured-domain guidance; anomalies and probabilities are unavailable.",
                ha="center",
                fontsize=8,
            )
            pdf.savefig(figure, dpi=160)
            plt.close(figure)
    return path


def update_catalogs(
    domain: dict[str, Any],
    source_id: str,
    payload: dict[str, Any],
    issue_id: str,
    forecast_relative: Path,
    geography_relative: Path,
    pdf_path: Path | None,
) -> None:
    registry_path = DATA / "domains.json"
    registry = read_json(registry_path)
    definition = {
        "id": domain["id"],
        "label": domain["label"],
        "kind": domain["kind"],
        "catalog": f"domains/{domain['id']}/index.json",
        "geography": geography_relative.as_posix(),
        "products": domain["products"],
        "pdf": domain["pdf"],
    }
    registry["domains"] = [
        item for item in registry["domains"] if item["id"] != domain["id"]
    ] + [definition]
    write_json(registry_path, registry)

    catalog_path = DATA / definition["catalog"]
    catalog = read_json(catalog_path) if catalog_path.is_file() else {
        "schema_version": 1,
        "default_view": "domain",
        "default_source": source_id,
        "latest_successful_issue": issue_id,
        "initial_condition_sources": [],
    }
    sources = {item["id"]: item for item in catalog["initial_condition_sources"]}
    source = sources.setdefault(
        source_id,
        {
            "id": source_id,
            **SOURCE_DEFINITIONS[source_id],
            "status": "experimental",
            "description": "Configured-domain raw forecast source",
            "default_issue": issue_id,
            "issues": [],
        },
    )
    issue = {
        "id": issue_id,
        "initialization": payload["issue"]["initialization"],
        "members": payload["issue"]["members"],
        "status": "warning",
        "role": "operational_experimental" if source_id != "era5" else "reference",
        "forecast": forecast_relative.as_posix(),
        "available_products": domain["products"],
        "capabilities": {"raw_fields": True, "anomalies": False, "pdf": bool(pdf_path)},
    }
    if pdf_path:
        issue["pdf"] = pdf_path.relative_to(PUBLIC).as_posix()
    source["issues"] = [item for item in source["issues"] if item["id"] != issue_id] + [issue]
    source["issues"].sort(key=lambda item: item["id"], reverse=True)
    source["default_issue"] = source["issues"][0]["id"]
    catalog["latest_successful_issue"] = max(
        item["id"]
        for catalog_source in sources.values()
        for item in catalog_source["issues"]
    )
    catalog["initial_condition_sources"] = [sources[key] for key in ("gfs", "era5", "ifs") if key in sources]
    catalog["generated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(catalog_path, catalog)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--forecast", type=Path, required=True)
    parser.add_argument("--source", choices=tuple(SOURCE_DEFINITIONS), required=True)
    args = parser.parse_args()
    domain = validate_config(read_json(args.config))
    payload, issue_id = forecast_payload(args.forecast, args.source, domain)
    geography, segments = build_geography(domain)
    geography_relative = Path("domains") / domain["id"] / "geography.json"
    forecast_relative = (
        Path("domains") / domain["id"] / "forecasts" / args.source / f"{issue_id}.json"
    )
    write_json(DATA / geography_relative, geography)
    pdf_path = (
        build_pdf(payload, args.source, issue_id, domain, segments)
        if domain["pdf"]
        else None
    )
    if pdf_path:
        payload["issue"]["downloads"].update(
            {
                "domain_pdf": pdf_path.relative_to(PUBLIC).as_posix(),
                "domain_pdf_sha256": sha256(pdf_path),
            }
        )
    write_json(DATA / forecast_relative, payload)
    update_catalogs(
        domain,
        args.source,
        payload,
        issue_id,
        forecast_relative,
        geography_relative,
        pdf_path,
    )
    print(DATA / forecast_relative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
