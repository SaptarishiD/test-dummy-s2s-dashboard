"""Small contract tests for the clean operational export bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import export_and_publish_operational_issue as bridge
from scripts.export_and_publish_operational_issue import (
    load_config,
    publisher_command,
    validate_wind_inputs,
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
    ("with_wind", "expected_scripts"),
    [
        (False, ["operational.py", "publish.py"]),
        (
            True,
            [
                "operational.py",
                "add_wind850_anomaly.py",
                "build_forecast_pdfs.py",
                "publish.py",
            ],
        ),
    ],
)
def test_wind_augmentation_and_pdf_rebuild_precede_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    with_wind: bool,
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
    forecast_json.write_text("{}", encoding="utf-8")
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
    if with_wind:
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
