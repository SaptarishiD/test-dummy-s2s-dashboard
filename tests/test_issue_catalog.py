"""Tests for the production Current pointer and archive metadata contract."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from science.catalog import (
    CADENCE_WEEKDAYS,
    build_catalog,
    enrich_issue,
    next_expected_update,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = PUBLIC / "data"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def on_cadence(issues: list[dict]) -> list[dict]:
    return [
        item
        for item in issues
        if datetime.strptime(item["id"], "%Y%m%d").weekday() in CADENCE_WEEKDAYS
    ]


def current_eligible(item: dict) -> bool:
    """100-member issues, IFS issues explicitly released as limited Current, or
    multi-model ensemble-mean issues (members: null)."""

    return (
        item["members"] == 100
        or item.get("limited_current") is True
        or item["members"] is None
    )


def member_class(source_id: str, item: dict) -> str:
    if source_id == "mme":
        return "ensemble_mean"
    return "production" if item["members"] == 100 else "limited"


def newest_current(index: dict) -> tuple[str, str]:
    """Newest eligible on-cadence (issue, source) over IFS and MME; MME wins ties."""

    priority = ("ifs", "mme")
    return max(
        (
            (item["id"], priority.index(source["id"]), source["id"])
            for source in index["initial_condition_sources"]
            if source["id"] in priority
            for item in on_cadence(source["issues"])
            if current_eligible(item)
        )
    )[0::2]


def test_current_is_latest_complete_on_cadence_production_ifs_issue() -> None:
    index = load(DATA / "index.json")
    issue_id, source_id = newest_current(index)
    source = next(
        item for item in index["initial_condition_sources"] if item["id"] == source_id
    )
    current_record = next(
        item for item in source["issues"] if item["id"] == index["current"]["issue_id"]
    )
    assert index["default_source"] == source_id
    assert index["current"]["source_id"] == source_id
    assert current_eligible(current_record)
    assert current_record["presentation"]["member_class"] == member_class(
        source_id, current_record
    )
    assert index["current"]["issue_id"] == issue_id
    assert index["latest_successful_issue"] == index["current"]["issue_id"]


def test_era5_pointer_is_a_complete_delayed_reference() -> None:
    index = load(DATA / "index.json")
    era5 = index["initial_condition_sources"][1]
    reference = index["latest_reference"]
    production = [item for item in era5["issues"] if item["members"] == 100]
    assert reference["source_id"] == "era5"
    assert reference["issue_id"] == max(item["id"] for item in production)
    assert era5["availability"]["mode"] == "delayed_reference"
    assert era5["availability"]["typical_lag_days"] == "5–7"


def test_catalog_assets_are_checksum_versioned_and_capability_scoped() -> None:
    index = load(DATA / "index.json")
    assert index["cache"] == {
        "catalog": "no-store",
        "assets": "checksum-versioned",
    }
    for source in index["initial_condition_sources"]:
        for issue in source["issues"]:
            forecast_path = DATA / issue["forecast"]
            expected = hashlib.sha256(forecast_path.read_bytes()).hexdigest()
            assert issue["checksums"]["forecast_sha256"] == expected
            assert {"rainfall_total", "temperature_mean"}.issubset(
                issue["available_products"]
            )
            assert issue["capabilities"]["raw_fields"] is True
            assert issue["presentation"]["member_class"] == member_class(
                source["id"], issue
            )
            assert issue["archive"]["metadata"] == "indefinite"


def test_catalog_rebuild_keeps_current_pointer_on_latest_on_cadence_ifs_issue() -> None:
    index = load(DATA / "index.json")
    ifs_source = next(
        source for source in index["initial_condition_sources"] if source["id"] == "ifs"
    )
    expected_issue, expected_source = newest_current(index)
    rebuilt = build_catalog(
        index,
        PUBLIC,
        datetime(2026, 8, 9, 0, tzinfo=timezone.utc),
    )
    assert rebuilt["default_source"] == expected_source
    assert rebuilt["current"]["source_id"] == expected_source
    assert rebuilt["current"]["issue_id"] == expected_issue
    rebuilt_ifs = next(
        source for source in rebuilt["initial_condition_sources"] if source["id"] == "ifs"
    )
    expected_ifs_issue = max(
        item["id"] for item in rebuilt_ifs["issues"] if current_eligible(item)
    )
    assert rebuilt_ifs["default_issue"] == expected_ifs_issue
    assert rebuilt["latest_reference"]["source_id"] == "era5"
    newer_limited = next(
        item
        for item in rebuilt["initial_condition_sources"][0]["issues"]
        if item["id"] == "20260802"
    )
    assert newer_limited["presentation"]["label"] == "Limited experiment"


def test_limited_issue_needs_explicit_release_to_become_current() -> None:
    index = load(DATA / "index.json")
    unflagged = copy.deepcopy(index)
    # Isolate the IFS rule: a multi-model issue would otherwise be Current.
    unflagged["initial_condition_sources"] = [
        source for source in unflagged["initial_condition_sources"] if source["id"] != "mme"
    ]
    ifs_source = next(
        source for source in unflagged["initial_condition_sources"] if source["id"] == "ifs"
    )
    for item in ifs_source["issues"]:
        item.pop("limited_current", None)
    rebuilt = build_catalog(
        unflagged,
        PUBLIC,
        datetime(2026, 8, 9, 0, tzinfo=timezone.utc),
    )
    assert rebuilt["current"]["members"] == 100
    assert rebuilt["current"]["issue_id"] == max(
        item["id"]
        for item in on_cadence(ifs_source["issues"])
        if item["members"] == 100
    )


def test_next_update_uses_wednesday_sunday_utc_cadence() -> None:
    assert next_expected_update(
        datetime(2026, 8, 5, 13, tzinfo=timezone.utc)
    ) == datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
    assert next_expected_update(
        datetime(2026, 8, 9, 11, 59, tzinfo=timezone.utc)
    ) == datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
    assert next_expected_update(
        datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
    ) == datetime(2026, 8, 12, 12, tzinfo=timezone.utc)


def test_forecast_schema_accepts_raw_only_year_round_payload() -> None:
    forecast = copy.deepcopy(load(DATA / "forecasts/gfs/20260805.json"))
    forecast["products"] = {
        key: value
        for key, value in forecast["products"].items()
        if key in {"rainfall_total", "temperature_mean"}
    }
    for week in forecast["weeks"]:
        week["fields"] = {
            key: value
            for key, value in week["fields"].items()
            if key in forecast["products"]
        }
        week["summary"] = {
            key: value
            for key, value in week["summary"].items()
            if key in forecast["products"]
        }
    schema = load(ROOT / "science/web-data.schema.json")
    jsonschema.Draft202012Validator(schema).validate(forecast)


def test_catalog_advertises_raw_and_anomalous_wind_independently(
    tmp_path: Path,
) -> None:
    forecast = copy.deepcopy(load(DATA / "forecasts/ifs/20260819.json"))
    forecast["products"]["wind850_mean"] = {
        "label": "Weekly mean 850 hPa wind"
    }
    forecast["issue"]["downloads"] = {
        "compact_json": "data/forecasts/ifs/20260819.json"
    }
    forecast_path = tmp_path / "data/forecasts/ifs/20260819.json"
    forecast_path.parent.mkdir(parents=True)
    forecast_path.write_text(json.dumps(forecast), encoding="utf-8")
    enriched, _ = enrich_issue(
        {
            "id": "20260819",
            "initialization": "2026-08-19T00:00:00Z",
            "members": 100,
            "forecast": "forecasts/ifs/20260819.json",
        },
        "ifs",
        tmp_path,
        datetime(2026, 8, 20, 0, tzinfo=timezone.utc),
    )
    assert enriched["capabilities"]["wind850_mean"] is True
    assert enriched["capabilities"]["wind850_anomaly"] is True
