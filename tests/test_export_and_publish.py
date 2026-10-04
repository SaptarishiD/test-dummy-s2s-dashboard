"""Small contract tests for the clean operational export bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import export_and_publish_operational_issue as bridge
from scripts.export_and_publish_operational_issue import (
    extreme_forecast_input,
    extreme_postprocess_command,
    load_config,
    publisher_command,
    validate_wind_inputs,
    wind_augmentation_available,
    wind_postprocess_commands,
)


def write_config(path: Path, *, source: str = "gfs", members: int = 100) -> None:
    path.write_text(
        json.dumps(
            {
                "members": members,
                "run_label": "fuxi_s2s_case_20260808_ens100",
                "input": {"builder": "gfs_daily_proxy"} if source == "gfs" else {},
            }
        ),
        encoding="utf-8",
    )


def forecast_payload(
    *,
    status: str,
    model_state_time: str,
) -> dict[str, object]:
    raw_products = ["rainfall_total", "temperature_mean"]
    target = model_state_time[5:10].replace("-", "")
    alignment = {
        "status": status,
        "target_model_state_calendar_day": target,
    }
    if status == "unavailable_outside_jjas":
        alignment.update(
            {
                "available_slot_start": "0602",
                "available_slot_end": "0929",
            }
        )
    return {
        "issue": {
            "model_state_time": model_state_time,
            "available_products": raw_products,
            "capabilities": {
                "raw_fields": True,
                "anomalies": False,
                "regional_probabilities_eligible": False,
            },
            "climatology_alignment": alignment,
        },
        "products": {product: {} for product in raw_products},
        "weeks": [
            {
                "week": week,
                "fields": {product: [] for product in raw_products},
                "summary": {product: {} for product in raw_products},
            }
            for week in range(1, 7)
        ],
    }


def test_private_config_identity_is_bound_before_export(tmp_path: Path) -> None:
    config = tmp_path / "case.json"
    write_config(config)
    assert load_config(config, "gfs", "20260808")["members"] == 100
    with pytest.raises(ValueError, match="source"):
        load_config(config, "era5", "20260808")
    write_config(config, members=5)
    with pytest.raises(ValueError, match="100-member"):
        load_config(config, "gfs", "20260808")


def test_publisher_command_carries_only_explicit_paths(tmp_path: Path) -> None:
    args = argparse.Namespace(
        publisher_script=Path("/opt/s2s/publish.py"),
        source="gfs",
        issue="20260808",
        publish_clone=Path("/srv/s2s/publisher"),
        remote="origin",
        branch="main",
        dashboard_subdir="clean/fuxi-dashboard",
        receipt=tmp_path / "receipt.json",
        clone_url=None,
        skip_install=False,
        skip_build=False,
        no_push=False,
    )
    command = publisher_command(args, tmp_path / "export")
    assert "--source-worktree" in command
    assert str(tmp_path / "export") in command
    assert "--receipt" in command
    assert "--no-push" not in command


def test_wind_inputs_are_optional_but_required_together_and_must_exist(
    tmp_path: Path,
) -> None:
    forecast = tmp_path / "wind-forecast.nc"
    climatology = tmp_path / "wind-climatology.nc"
    forecast.touch()
    climatology.touch()

    assert validate_wind_inputs(
        argparse.Namespace(wind_forecast=None, wind_climatology=None)
    ) is None
    with pytest.raises(ValueError, match="supplied together"):
        validate_wind_inputs(
            argparse.Namespace(
                wind_forecast=forecast,
                wind_climatology=None,
            )
        )
    with pytest.raises(ValueError, match="wind forecast is not a file"):
        validate_wind_inputs(
            argparse.Namespace(
                wind_forecast=tmp_path / "missing.nc",
                wind_climatology=climatology,
            )
        )
    assert validate_wind_inputs(
        argparse.Namespace(
            wind_forecast=forecast,
            wind_climatology=climatology,
        )
    ) == (forecast.resolve(), climatology.resolve())


def test_extreme_forecast_uses_validated_ifs_member_file(
    tmp_path: Path,
) -> None:
    forecast = tmp_path / "forecast.nc"
    climatology = tmp_path / "climatology.nc"
    forecast.touch()
    climatology.touch()
    wind_inputs = (forecast.resolve(), climatology.resolve())
    assert extreme_forecast_input(
        argparse.Namespace(source="ifs", extreme_forecast=None), wind_inputs
    ) == forecast.resolve()
    assert extreme_forecast_input(
        argparse.Namespace(source="gfs", extreme_forecast=forecast), wind_inputs
    ) is None


@pytest.mark.parametrize("with_regional", [True, False])
def test_extreme_postprocess_is_issue_scoped_and_skips_ineligible_dates(
    tmp_path: Path,
    with_regional: bool,
) -> None:
    dashboard = tmp_path / "dashboard"
    forecast_json = dashboard / "public/data/forecasts/ifs/20260930.json"
    regional_json = dashboard / "public/data/regional/ifs/20260930.json"
    builder_script = dashboard / "scripts/build_extreme_products.py"
    for path in (forecast_json, builder_script):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    if with_regional:
        regional_json.parent.mkdir(parents=True, exist_ok=True)
        regional_json.touch()
    private_forecast = tmp_path / "20260930.nc"
    private_forecast.touch()
    command = extreme_postprocess_command(
        argparse.Namespace(
            source="ifs",
            issue="20260930",
            operational_python="/opt/s2s/python",
        ),
        dashboard,
        private_forecast,
    )
    assert command[0] == "/opt/s2s/python"
    assert command[1] == str(builder_script)
    assert command[command.index("--forecast") + 1] == str(private_forecast)
    assert command[command.index("--public-forecast") + 1] == str(forecast_json)
    assert command[command.index("--regional") + 1] == str(regional_json)
    assert "--skip-ineligible" in command


def test_wind_postprocessing_requires_the_generated_issue_json(
    tmp_path: Path,
) -> None:
    forecast = tmp_path / "wind-forecast.nc"
    climatology = tmp_path / "wind-climatology.nc"
    forecast.touch()
    climatology.touch()
    dashboard = tmp_path / "dashboard"
    (dashboard / "scripts").mkdir(parents=True)
    (dashboard / "scripts/build_forecast_pdfs.py").touch()
    index = dashboard / "public/data/index.json"
    index.parent.mkdir(parents=True)
    index.touch()

    with pytest.raises(ValueError, match="published forecast JSON"):
        wind_postprocess_commands(
            argparse.Namespace(
                source="gfs",
                issue="20260808",
                operational_python="/opt/s2s/python",
            ),
            dashboard,
            (forecast.resolve(), climatology.resolve()),
        )


@pytest.mark.parametrize(
    ("model_state_time", "status", "expected"),
    [
        ("2026-09-29T00:00:00Z", "available", True),
        ("2026-10-02T00:00:00Z", "unavailable_outside_jjas", False),
    ],
)
def test_wind_augmentation_follows_base_climatology_alignment(
    tmp_path: Path,
    model_state_time: str,
    status: str,
    expected: bool,
) -> None:
    forecast_json = tmp_path / "forecast.json"
    forecast_json.write_text(
        json.dumps(forecast_payload(status=status, model_state_time=model_state_time)),
        encoding="utf-8",
    )

    assert wind_augmentation_available(forecast_json) is expected


def test_wind_augmentation_rejects_unknown_alignment_status(tmp_path: Path) -> None:
    forecast_json = tmp_path / "forecast.json"
    forecast_json.write_text(
        json.dumps(
            forecast_payload(
                status="not_validated",
                model_state_time="2026-08-25T00:00:00Z",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported climatology alignment"):
        wind_augmentation_available(forecast_json)


def test_outside_jjas_status_cannot_bypass_in_window_wind_gate(
    tmp_path: Path,
) -> None:
    forecast_json = tmp_path / "forecast.json"
    forecast_json.write_text(
        json.dumps(
            forecast_payload(
                status="unavailable_outside_jjas",
                model_state_time="2026-08-25T00:00:00Z",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="inside the available slot bounds"):
        wind_augmentation_available(forecast_json)


def test_outside_jjas_fallback_rejects_declared_anomaly_products(
    tmp_path: Path,
) -> None:
    payload = forecast_payload(
        status="unavailable_outside_jjas",
        model_state_time="2026-10-02T00:00:00Z",
    )
    payload["products"]["wind850_anomaly"] = {}
    forecast_json = tmp_path / "forecast.json"
    forecast_json.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="not a raw-only product package"):
        wind_augmentation_available(forecast_json)


@pytest.mark.parametrize("value", [True, 1, "yes"])
def test_outside_jjas_fallback_rejects_wind_capability_values(
    tmp_path: Path,
    value: object,
) -> None:
    payload = forecast_payload(
        status="unavailable_outside_jjas",
        model_state_time="2026-10-02T00:00:00Z",
    )
    payload["issue"]["capabilities"]["wind850_mean"] = value
    forecast_json = tmp_path / "forecast.json"
    forecast_json.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="capabilities are not raw-only"):
        wind_augmentation_available(forecast_json)


@pytest.mark.parametrize(
    ("with_wind", "alignment_status", "expected_scripts"),
    [
        (False, "available", ["operational.py", "publish.py"]),
        (
            True,
            "available",
            [
                "operational.py",
                "add_wind850_anomaly.py",
                "build_forecast_pdfs.py",
                "publish.py",
            ],
        ),
        (
            True,
            "unavailable_outside_jjas",
            ["operational.py", "publish.py"],
        ),
    ],
)
def test_wind_augmentation_and_pdf_rebuild_precede_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_wind: bool,
    alignment_status: str,
    expected_scripts: list[str],
) -> None:
    config = tmp_path / "case.json"
    write_config(config)
    receipt = tmp_path / "receipt.json"
    publish_clone = tmp_path / "publisher"
    export_dashboard = tmp_path / "export"
    (export_dashboard / "scripts").mkdir(parents=True)
    (export_dashboard / "package.json").touch()
    (export_dashboard / "scripts/build_forecast_pdfs.py").touch()
    forecast_json = (
        export_dashboard / "public/data/forecasts/gfs/20260808.json"
    )
    forecast_json.parent.mkdir(parents=True)
    model_state_time = (
        "2026-10-02T00:00:00Z"
        if alignment_status == "unavailable_outside_jjas"
        else "2026-08-07T00:00:00Z"
    )
    forecast_json.write_text(
        json.dumps(
            forecast_payload(
                status=alignment_status,
                model_state_time=model_state_time,
            )
        ),
        encoding="utf-8",
    )
    index = export_dashboard / "public/data/index.json"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text("{}", encoding="utf-8")

    wind_forecast = tmp_path / "wind-forecast.nc"
    wind_climatology = tmp_path / "wind-climatology.nc"
    if with_wind:
        wind_forecast.touch()
        wind_climatology.touch()
    args = argparse.Namespace(
        source="gfs",
        issue="20260808",
        config=config,
        operational_script=Path("/opt/s2s/operational.py"),
        operational_python="/opt/s2s/python",
        publisher_script=Path("/opt/s2s/publish.py"),
        publish_clone=publish_clone,
        clone_url=None,
        remote="origin",
        branch="main",
        dashboard_subdir=".",
        expected_base_sha=None,
        receipt=receipt,
        timeout=60,
        wind_forecast=wind_forecast if with_wind else None,
        wind_climatology=wind_climatology if with_wind else None,
        skip_install=False,
        skip_build=False,
        no_push=True,
    )
    calls: list[list[str]] = []
    removed: list[tuple[Path, Path]] = []

    monkeypatch.setattr(bridge, "parse_args", lambda: args)
    monkeypatch.setattr(
        bridge,
        "prepare_clone",
        lambda _args: (publish_clone, "a" * 40),
    )
    monkeypatch.setattr(
        bridge,
        "create_disposable_worktree",
        lambda _root, _sha: export_dashboard,
    )
    monkeypatch.setattr(
        bridge,
        "remove_disposable_worktree",
        lambda root, worktree: removed.append((root, worktree)),
    )

    def record_run(command: list[str], **_kwargs: object) -> None:
        calls.append(command)
        if str(args.publisher_script) in command:
            receipt.write_text(
                json.dumps({"source": "gfs", "issue": "20260808"}),
                encoding="utf-8",
            )

    monkeypatch.setattr(bridge.subprocess, "run", record_run)

    assert bridge.main() == 0

    assert [Path(command[1]).name for command in calls] == expected_scripts
    assert removed == [(publish_clone, export_dashboard)]
    if with_wind and alignment_status == "available":
        augmentation = calls[1]
        assert augmentation[0] == args.operational_python
        assert augmentation[augmentation.index("--forecast-json") + 1] == str(
            forecast_json
        )
        assert augmentation[augmentation.index("--wind-forecast") + 1] == str(
            wind_forecast.resolve()
        )
        assert augmentation[augmentation.index("--wind-climatology") + 1] == str(
            wind_climatology.resolve()
        )
        pdf = calls[2]
        assert pdf[0] == args.operational_python
        assert pdf[pdf.index("--index") + 1] == str(index)
        assert pdf[pdf.index("--source") + 1] == "gfs"
        assert pdf[pdf.index("--issue") + 1] == "20260808"
