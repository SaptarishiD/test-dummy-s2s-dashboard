#!/usr/bin/env python3
"""Import a multi-model ensemble-mean weekly package as a compact public issue.

The package (``products.nc``) holds weekly ensemble-mean fields that were already
averaged across several forecast systems on the published 27x27 India grid:
rainfall (mm/day), 2 m temperature (degC), their anomalies against a 2011-2025
calendar-day reanalysis climatology, and 850 hPa wind speed/U/V with the same
baseline.  Only weeks 1-4 are published.  The issue is written under source id
``mme`` with no member count (``members: null``): there are no members, spread,
extremes or probabilities, and none are synthesised.

The public text deliberately names no forecast system or reanalysis product.
No NetCDF attribute is copied, because the package embeds private host paths
and internal provenance.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.import_external_issue import flatten, load_json, summary  # noqa: E402
from science.validators import write_json  # noqa: E402

DATA = ROOT / "public" / "data"
SOURCE_ID = "mme"
WEEKS = 4
LABEL = "AI S2S multi-model ensemble mean"
DESCRIPTION = (
    "AI-based multi-model ensemble combining several AI and physics-based S2S "
    "forecast systems"
)
BASELINE = "2011–2025 average for the same calendar days"
KEYS = (
    "rainfall_total",
    "temperature_mean",
    "rainfall_anomaly",
    "temperature_anomaly",
    "wind850_mean",
    "wind850_anomaly",
)
VECTORS = {
    "wind850_mean": ("u_mean", "v_mean"),
    "wind850_anomaly": ("u_anom", "v_anom"),
}
DESCRIPTIONS = {
    "rainfall_total": "Multi-model ensemble-mean seven-day accumulation",
    "temperature_mean": "Multi-model ensemble-mean 2-metre temperature",
    "rainfall_anomaly": "Weekly-mean forecast minus a seasonally matched calendar-day climatology",
    "temperature_anomaly": "Weekly-mean forecast minus a seasonally matched calendar-day climatology",
    "wind850_mean": (
        "Shading is the speed of the weekly ensemble-mean wind vector; arrows are "
        "the weekly ensemble-mean U/V components"
    ),
    "wind850_anomaly": (
        "Shading is the weekly ensemble-mean vector speed minus the climatological "
        "mean of yearly vector speeds; arrows are the U/V anomaly from the "
        "climatological mean"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(args: argparse.Namespace) -> dict[str, Any]:
    template = load_json(args.template)
    grid = template["grid"]
    latitude = np.asarray(grid["latitude"], dtype=np.float64)
    longitude = np.asarray(grid["longitude"], dtype=np.float64)
    shape = (latitude.size, longitude.size)
    mask = np.asarray(grid["india_mask"], dtype=bool).reshape(shape)

    package = xr.open_dataset(args.products).load()
    initialization = date.fromisoformat(str(package.attrs["init"]))
    if initialization.strftime("%Y%m%d") != args.issue:
        raise ValueError(f"package initialization {initialization} is not {args.issue}")
    if str(package.attrs.get("source")) != SOURCE_ID:
        raise ValueError("package is not a multi-model ensemble-mean package")
    if not (
        np.allclose(package["lat"].values, latitude)
        and np.allclose(package["lon"].values, longitude)
    ):
        raise ValueError("package grid differs from the published India grid")
    if package.sizes["week"] < WEEKS:
        raise ValueError(f"package has fewer than {WEEKS} weeks")
    if not bool(np.all(package["anomaly_reference_complete"].values[:WEEKS] == 1)):
        raise ValueError("anomaly reference is incomplete in weeks 1-4")
    composition = json.loads(package.attrs["composition"])[:WEEKS]

    def field(name: str, index: int) -> np.ndarray:
        values = np.asarray(
            package[name].isel(week=index).transpose("lat", "lon").values, dtype=np.float64
        )
        if values.shape != shape or not np.isfinite(values).all():
            raise ValueError(f"{name} week {index + 1} is incomplete")
        return values

    weeks = []
    for index in range(WEEKS):
        start = date.fromisoformat(str(package["valid_start"].values[index])[:10])
        end_exclusive = date.fromisoformat(str(package["valid_end"].values[index])[:10])
        end = end_exclusive - timedelta(days=1)  # site publishes the inclusive last day
        if start != initialization + timedelta(days=7 * index) or (end - start).days != 6:
            raise ValueError(f"week {index + 1} is not a complete seven-day week")
        if composition[index]["week"] != index + 1 or composition[index]["valid"] != [
            start.isoformat(),
            end.isoformat(),
        ]:
            raise ValueError(f"composition record differs for week {index + 1}")
        fields = {key: field(key, index) for key in KEYS}
        # Package rainfall is a weekly-mean rate; the site stores the 7-day total.
        fields["rainfall_total"] = fields["rainfall_total"] * 7.0
        if (fields["wind850_mean"] < 0).any() or (fields["rainfall_total"] < 0).any():
            raise ValueError(f"negative rainfall or wind speed in week {index + 1}")
        weeks.append(
            {
                "week": index + 1,
                "valid_start": start.isoformat(),
                "valid_end": end.isoformat(),
                "fields": {key: flatten(fields[key]) for key in KEYS},
                "summary": {key: summary(fields[key], mask, latitude) for key in KEYS},
                "vectors": {
                    key: {"u": flatten(field(u, index)), "v": flatten(field(v, index))}
                    for key, (u, v) in VECTORS.items()
                },
            }
        )

    products: dict[str, Any] = {}
    for key in KEYS:
        definition = copy.deepcopy(template["products"][key])
        definition["description"] = DESCRIPTIONS[key]
        definition["baseline"] = BASELINE if key.endswith("_anomaly") else None
        products[key] = definition

    pdf_relative = f"downloads/{SOURCE_ID}/{args.issue}/S2S_Research_India_Weeks1-4_MME_{args.issue}.pdf"
    pdf_path = ROOT / "public" / pdf_relative
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    speed = np.stack([np.asarray(week["fields"]["wind850_mean"]) for week in weeks])
    speed_anomaly = np.stack([np.asarray(week["fields"]["wind850_anomaly"]) for week in weeks])
    timestamp = f"{initialization.isoformat()}T00:00:00Z"
    return {
        "schema_version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue": {
            "initialization": timestamp,
            "information_cutoff": timestamp,
            "model_state_time": timestamp,
            "input_days": [],
            "input_source": DESCRIPTION,
            "members": None,
            "ensemble_representation": "multi_model_ensemble_mean",
            "lead_days": WEEKS * 7,
            "status": "warning",
            "scientific_status": (
                "Ensemble-mean fields only. This issue has no "
                "probability, spread or extreme products."
            ),
            "initial_condition_source": {
                "label": LABEL,
                "short_label": "Multi-model",
                "category": "multi_model_ensemble",
                "availability": "near_real_time",
                "description": DESCRIPTION,
                "id": SOURCE_ID,
            },
            "downloads": {
                "compact_json": f"data/forecasts/{SOURCE_ID}/{args.issue}.json",
                "india_pdf": pdf_relative,
                "india_pdf_sha256": sha256(pdf_path),
            },
            "available_products": list(KEYS),
            "capabilities": {
                "raw_fields": True,
                "anomalies": True,
                "regional_probabilities_eligible": False,
                "wind850_mean": True,
                "wind850_anomaly": True,
                "extreme_products": False,
                "joint_outcomes": False,
                "ensemble_spread": False,
            },
            "climatology_alignment": {
                "status": "calendar_day_reference",
                "target_initialization_calendar_day": initialization.strftime("%m%d"),
                "operation_order": (
                    "for each forecast system, subtract the 2011–2025 mean for each "
                    "exact valid calendar day and aggregate seven days of the "
                    "ensemble mean; then average the systems"
                ),
                "message": "Anomalies are relative to the 2011–2025 average for the same calendar days.",
            },
            "anomaly_baseline_note": "Anomaly taken against climatology data for the respective variables",
            "multi_model_composition": [
                {
                    "week": row["week"],
                    "rainfall_temperature_systems": len(row["rainfall_total"]),
                    "wind850_systems": len(row["wind850"]),
                }
                for row in composition
            ],
            "observation_verification": {
                "status": "not_available",
                "message": (
                    "Verification is withheld until every required observation day "
                    "in a valid week is available."
                ),
            },
        },
        "grid": copy.deepcopy(grid),
        "products": products,
        "diagnostics": {
            "wind850_mean_speed_min_m_s": round(float(speed.min()), 4),
            "wind850_mean_speed_max_m_s": round(float(speed.max()), 4),
            "wind850_speed_anomaly_min_m_s": round(float(speed_anomaly.min()), 4),
            "wind850_speed_anomaly_max_m_s": round(float(speed_anomaly.max()), 4),
        },
        "weeks": weeks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=Path, required=True, help="products.nc")
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
    output = args.output or DATA / "forecasts" / SOURCE_ID / f"{args.issue}.json"
    write_json(output, payload)
    print(f"wrote {output} ({len(payload['weeks'])} weeks, ensemble mean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
