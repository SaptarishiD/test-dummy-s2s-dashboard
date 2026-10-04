#!/usr/bin/env python3
"""Export one validated private FuXi run and publish it from clean worktrees.

The scientific checkout is never used as a web-export destination.  A
disposable worktree based on the latest publication branch receives the
derived JSON/PDF package, then ``publish_operational_site.py`` copies only its
allow-listed public assets into a second disposable worktree for validation,
commit, and a normal non-force push.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.publish_operational_site import (  # noqa: E402
    create_disposable_worktree,
    prepare_clone,
    remove_disposable_worktree,
)

VALIDATED_JJAS_SLOT_START = "0602"
VALIDATED_JJAS_SLOT_END = "0929"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("gfs", "era5", "ifs"), required=True)
    parser.add_argument("--issue", required=True, help="Initialization YYYYMMDD.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--operational-script",
        type=Path,
        default=Path(
            os.environ.get(
                "S2S_OPERATIONAL_SCRIPT",
                ROOT.parent / "model-runs/fuxi/scripts/fuxi_operational.py",
            )
        ),
    )
    parser.add_argument(
        "--operational-python",
        default=os.environ.get("S2S_DRIVER_PYTHON", sys.executable),
    )
    parser.add_argument(
        "--publisher-script",
        type=Path,
        default=ROOT / "scripts/publish_operational_site.py",
    )
    parser.add_argument(
        "--publish-clone",
        type=Path,
        default=os.environ.get("S2S_PUBLISH_CLONE"),
    )
    parser.add_argument("--clone-url", default=os.environ.get("S2S_REPOSITORY_URL"))
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--branch", default=os.environ.get("S2S_PUBLISH_BRANCH", "main")
    )
    parser.add_argument(
        "--dashboard-subdir",
        default=os.environ.get("S2S_DASHBOARD_SUBDIR", "."),
    )
    parser.add_argument("--expected-base-sha")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument(
        "--wind-forecast",
        type=Path,
        help="Validated U850/V850 forecast NetCDF; requires --wind-climatology.",
    )
    parser.add_argument(
        "--wind-climatology",
        type=Path,
        help="Matched 2002-2021 wind climatology; requires --wind-forecast.",
    )
    parser.add_argument(
        "--extreme-forecast",
        type=Path,
        help=(
            "Validated TP/T2M member forecast for automatic IFS EFI/SOT. "
            "Defaults to --wind-forecast when that file is supplied."
        ),
    )
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    return parser.parse_args()


def load_config(path: Path, source: str, issue: str) -> dict[str, Any]:
    """Validate the immutable 100-member config before any Git operation."""

    if len(issue) != 8 or not issue.isdigit():
        raise ValueError("issue must use YYYYMMDD")
    payload = json.loads(path.read_text(encoding="utf-8"))
    configured_source = {
        "gfs_daily_proxy": "gfs",
        "ifs_daily_proxy": "ifs",
        "era5_daily": "era5",
    }.get(payload.get("input", {}).get("builder", "era5_daily"), "era5")
    if configured_source != source:
        raise ValueError(f"config source is {configured_source}, expected {source}")
    if int(payload.get("members", 0)) != 100:
        raise ValueError("only validated 100-member runs may be published")
    if issue not in str(payload.get("run_label", "")):
        raise ValueError("config run label does not match the requested issue")
    return payload


def publisher_command(
    args: argparse.Namespace,
    source_dashboard: Path,
) -> list[str]:
    command = [
        sys.executable,
        str(args.publisher_script),
        "--source",
        args.source,
        "--issue",
        args.issue,
        "--source-worktree",
        str(source_dashboard),
        "--publish-clone",
        str(args.publish_clone),
        "--remote",
        args.remote,
        "--branch",
        args.branch,
        "--dashboard-subdir",
        args.dashboard_subdir,
        "--receipt",
        str(args.receipt),
    ]
    if args.clone_url:
        command.extend(["--clone-url", args.clone_url])
    if args.skip_install:
        command.append("--skip-install")
    if args.skip_build:
        command.append("--skip-build")
    if args.no_push:
        command.append("--no-push")
    return command


def validate_wind_inputs(args: argparse.Namespace) -> tuple[Path, Path] | None:
    """Resolve an optional, required-together wind forecast/climatology pair."""

    forecast_value = getattr(args, "wind_forecast", None)
    climatology_value = getattr(args, "wind_climatology", None)
    if (forecast_value is None) != (climatology_value is None):
        raise ValueError(
            "--wind-forecast and --wind-climatology must be supplied together"
        )
    if forecast_value is None:
        return None

    resolved: list[Path] = []
    for label, value in (
        ("wind forecast", forecast_value),
        ("wind climatology", climatology_value),
    ):
        path = Path(value).resolve()
        if not path.is_file():
            raise ValueError(f"{label} is not a file: {path}")
        resolved.append(path)
    return resolved[0], resolved[1]


def wind_postprocess_commands(
    args: argparse.Namespace,
    export_dashboard: Path,
    wind_inputs: tuple[Path, Path],
) -> list[list[str]]:
    """Build ordered wind augmentation and issue-specific PDF commands."""

    wind_forecast, wind_climatology = wind_inputs
    forecast_json = (
        export_dashboard
        / "public"
        / "data"
        / "forecasts"
        / args.source
        / f"{args.issue}.json"
    )
    index = export_dashboard / "public" / "data" / "index.json"
    add_wind_script = ROOT / "scripts" / "add_wind850_anomaly.py"
    pdf_script = export_dashboard / "scripts" / "build_forecast_pdfs.py"
    for label, path in (
        ("published forecast JSON", forecast_json),
        ("published issue catalog", index),
        ("wind augmentation script", add_wind_script),
        ("PDF builder", pdf_script),
    ):
        if not path.is_file():
            raise ValueError(f"{label} is not a file: {path}")

    return [
        [
            args.operational_python,
            str(add_wind_script),
            "--forecast-json",
            str(forecast_json),
            "--wind-forecast",
            str(wind_forecast),
            "--wind-climatology",
            str(wind_climatology),
        ],
        [
            args.operational_python,
            str(pdf_script),
            "--index",
            str(index),
            "--source",
            args.source,
            "--issue",
            args.issue,
        ],
    ]


def extreme_forecast_input(
    args: argparse.Namespace,
    wind_inputs: tuple[Path, Path] | None,
) -> Path | None:
    """Resolve the member forecast used by the optional IFS extreme step."""

    if args.source != "ifs":
        return None
    configured = getattr(args, "extreme_forecast", None)
    candidate = Path(configured) if configured is not None else (
        wind_inputs[0] if wind_inputs is not None else None
    )
    if candidate is None:
        return None
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise ValueError(f"extreme forecast is not a file: {resolved}")
    return resolved


def extreme_postprocess_command(
    args: argparse.Namespace,
    export_dashboard: Path,
    forecast: Path,
) -> list[str]:
    """Build the automatic EFI/SOT command for an exported IFS issue."""

    forecast_json = (
        export_dashboard
        / "public/data/forecasts"
        / args.source
        / f"{args.issue}.json"
    )
    regional_json = (
        export_dashboard
        / "public/data/regional"
        / args.source
        / f"{args.issue}.json"
    )
    builder = export_dashboard / "scripts/build_extreme_products.py"
    for label, path in (
        ("published forecast JSON", forecast_json),
        ("extreme product builder", builder),
    ):
        if not path.is_file():
            raise ValueError(f"{label} is not a file: {path}")
    # The builder checks date eligibility before reading regional_json. Outside
    # the validated climatology no regional package is exported, and the
    # --skip-ineligible path must remain available for those raw-only issues.
    return [
        args.operational_python,
        str(builder),
        "--forecast",
        str(forecast),
        "--public-forecast",
        str(forecast_json),
        "--regional",
        str(regional_json),
        "--skip-ineligible",
    ]


def wind_augmentation_available(forecast_json: Path) -> bool:
    """Return whether the base export has a supported anomaly climatology.

    The native rainfall/temperature exporter is the authority for the
    model-state calendar alignment. Outside its validated JJAS window it
    deliberately emits a raw-only package; the optional wind bridge must
    preserve that fallback instead of interpolating beyond the same boundary.
    """

    try:
        payload = json.loads(
            forecast_json.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value!r}")
            ),
        )
        issue = payload["issue"]
        alignment = issue["climatology_alignment"]
        status = alignment["status"]
    except (KeyError, TypeError) as error:
        raise ValueError(
            "published forecast lacks climatology alignment status"
        ) from error

    model_state_time = issue.get("model_state_time")
    if not isinstance(model_state_time, str):
        raise ValueError("published forecast lacks a valid model-state time")
    try:
        model_state_day = datetime.strptime(model_state_time[:10], "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("published forecast has an invalid model-state time") from error
    target = alignment.get("target_model_state_calendar_day")
    if target != model_state_day.strftime("%m%d"):
        raise ValueError("climatology alignment target differs from model-state time")

    if status == "available":
        return True
    if status == "unavailable_outside_jjas":
        def calendar_day(value: object, label: str) -> datetime:
            if not isinstance(value, str) or len(value) != 4 or not value.isdigit():
                raise ValueError(f"climatology alignment has an invalid {label}")
            try:
                return datetime.strptime(f"2000{value}", "%Y%m%d")
            except ValueError as error:
                raise ValueError(
                    f"climatology alignment has an invalid {label}"
                ) from error

        target_day = calendar_day(target, "target calendar day")
        available_start = calendar_day(
            alignment.get("available_slot_start"), "available-slot start"
        )
        available_end = calendar_day(
            alignment.get("available_slot_end"), "available-slot end"
        )
        if (
            alignment.get("available_slot_start") != VALIDATED_JJAS_SLOT_START
            or alignment.get("available_slot_end") != VALIDATED_JJAS_SLOT_END
        ):
            raise ValueError(
                "climatology alignment bounds differ from the validated JJAS slots"
            )
        if available_start > available_end:
            raise ValueError("climatology alignment slot bounds are reversed")
        if available_start <= target_day <= available_end:
            raise ValueError(
                "outside-JJAS alignment target is inside the available slot bounds"
            )

        raw_products = {"rainfall_total", "temperature_mean"}
        products = payload.get("products")
        available_products = issue.get("available_products")
        capabilities = issue.get("capabilities")
        weeks = payload.get("weeks")
        if not isinstance(products, dict) or set(products) != raw_products:
            raise ValueError("outside-JJAS forecast is not a raw-only product package")
        if (
            not isinstance(available_products, list)
            or len(available_products) != len(raw_products)
            or set(available_products) != raw_products
        ):
            raise ValueError("outside-JJAS available products are not raw-only")
        if (
            not isinstance(capabilities, dict)
            or capabilities.get("raw_fields") is not True
            or capabilities.get("anomalies") is not False
            or capabilities.get("regional_probabilities_eligible") is not False
            or capabilities.get("wind850_mean", False) is not False
            or capabilities.get("wind850_anomaly", False) is not False
        ):
            raise ValueError("outside-JJAS forecast capabilities are not raw-only")
        if not isinstance(weeks, list) or len(weeks) != 6:
            raise ValueError("outside-JJAS forecast must contain exactly six weeks")
        for expected_week, week in enumerate(weeks, start=1):
            if not isinstance(week, dict) or week.get("week") != expected_week:
                raise ValueError("outside-JJAS forecast weeks are not ordered")
            fields = week.get("fields")
            summaries = week.get("summary")
            if (
                not isinstance(fields, dict)
                or not isinstance(summaries, dict)
                or set(fields) != raw_products
                or set(summaries) != raw_products
            ):
                raise ValueError("outside-JJAS forecast week is not raw-only")
            if week.get("vectors"):
                raise ValueError("outside-JJAS forecast unexpectedly contains vectors")
        return False
    raise ValueError(f"unsupported climatology alignment status: {status!r}")


def main() -> int:
    args = parse_args()
    load_config(args.config, args.source, args.issue)
    wind_inputs = validate_wind_inputs(args)
    extreme_forecast = extreme_forecast_input(args, wind_inputs)
    if args.timeout < 1:
        raise ValueError("timeout must be positive")
    if args.publish_clone is None:
        raise ValueError("--publish-clone or S2S_PUBLISH_CLONE is required")

    clone_args = SimpleNamespace(
        publish_clone=args.publish_clone,
        clone_url=args.clone_url,
        remote=args.remote,
        branch=args.branch,
        expected_base_sha=args.expected_base_sha,
    )
    publish_root, base_sha = prepare_clone(clone_args)
    export_worktree = create_disposable_worktree(publish_root, base_sha)
    try:
        dashboard_subdir = Path(args.dashboard_subdir)
        if dashboard_subdir.is_absolute() or ".." in dashboard_subdir.parts:
            raise ValueError("dashboard subdirectory must stay inside the worktree")
        export_dashboard = (export_worktree / dashboard_subdir).resolve()
        if not (export_dashboard / "package.json").is_file():
            raise ValueError(f"dashboard is absent from export worktree: {export_dashboard}")
        environment = os.environ.copy()
        environment["S2S_DASHBOARD_ROOT"] = str(export_dashboard)
        subprocess.run(
            [
                args.operational_python,
                str(args.operational_script),
                "publish",
                "--configs",
                str(args.config.resolve()),
                "--date",
                args.issue,
            ],
            cwd=export_dashboard,
            env=environment,
            check=True,
            timeout=args.timeout,
        )
        if wind_inputs is not None:
            forecast_json = (
                export_dashboard
                / "public"
                / "data"
                / "forecasts"
                / args.source
                / f"{args.issue}.json"
            )
            if wind_augmentation_available(forecast_json):
                for command in wind_postprocess_commands(
                    args, export_dashboard, wind_inputs
                ):
                    subprocess.run(
                        command,
                        cwd=export_dashboard,
                        env=environment,
                        check=True,
                        timeout=args.timeout,
                    )
            else:
                print(
                    "wind augmentation withheld outside the validated JJAS "
                    "climatology; publishing the base raw-only package",
                    flush=True,
                )
        if extreme_forecast is not None:
            subprocess.run(
                extreme_postprocess_command(
                    args, export_dashboard, extreme_forecast
                ),
                cwd=export_dashboard,
                env=environment,
                check=True,
                timeout=args.timeout,
            )
        subprocess.run(
            publisher_command(args, export_dashboard),
            cwd=ROOT,
            check=True,
            timeout=args.timeout,
        )
    finally:
        remove_disposable_worktree(publish_root, export_worktree)

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if receipt.get("source") != args.source or receipt.get("issue") != args.issue:
        raise ValueError("publisher receipt identity mismatch")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as error:
        raise SystemExit(f"operational export/publication failed: {error}") from error
