from __future__ import annotations

import numpy as np
import json
from pathlib import Path

from science.extremes import (
    complete_weekly_samples,
    extreme_forecast_index,
    paired_tercile_matrix,
    quantiles,
    shift_of_tails,
)


def earthkit_reference_efi(climate: np.ndarray, forecast: np.ndarray) -> np.ndarray:
    """Independent transcription of the public Earthkit array algorithm."""

    climate_percentiles = np.quantile(
        climate, np.linspace(0.0, 1.0, 101), axis=0, method="linear"
    )
    fraction = np.asarray(
        [(forecast <= threshold).mean(axis=0) for threshold in climate_percentiles]
    )
    probability = np.linspace(0.0, 1.0, 101)
    derivative = np.diff(fraction, axis=0) * 100.0
    acos_difference = np.diff(np.arccos(np.sqrt(probability)))
    product_difference = np.diff(np.sqrt(probability * (1.0 - probability)))
    coefficient = (
        (1.0 - 2.0 * probability[:-1]) * acos_difference
        + product_difference
    )
    return (2.0 / np.pi) * np.sum(
        (2.0 * fraction[:-1] - 1.0) * acos_difference[:, None]
        + coefficient[:, None] * derivative
        - product_difference[:, None],
        axis=0,
    )


def test_efi_matches_earthkit_on_deterministic_arrays() -> None:
    climate = np.stack(
        [np.linspace(-3.0, 3.0, 306), np.linspace(0.0, 20.0, 306)], axis=1
    )
    forecast = np.stack(
        [np.linspace(-1.5, 4.0, 51), np.linspace(4.0, 16.0, 51)], axis=1
    )
    np.testing.assert_allclose(
        extreme_forecast_index(forecast, climate),
        earthkit_reference_efi(climate, forecast),
        rtol=0.0,
        atol=1e-14,
    )


def test_efi_identical_and_extreme_distributions() -> None:
    climate = np.linspace(-2.0, 2.0, 101)[:, None]
    assert abs(float(extreme_forecast_index(climate, climate)[0])) < 0.02
    assert float(extreme_forecast_index(np.full((51, 1), 5.0), climate)[0]) > 0.99
    assert float(extreme_forecast_index(np.full((51, 1), -5.0), climate)[0]) < -0.99


def test_shift_of_tails_known_quantiles_and_degenerate_denominator() -> None:
    climate = np.arange(101, dtype=float)[:, None]
    upper_forecast = np.full((51, 1), 108.9)
    lower_forecast = np.full((51, 1), -8.9)
    np.testing.assert_allclose(shift_of_tails(upper_forecast, climate, tail="upper"), [1.1])
    np.testing.assert_allclose(shift_of_tails(lower_forecast, climate, tail="lower"), [1.1])
    assert np.isnan(
        shift_of_tails(np.ones((51, 1)), np.ones((101, 1)), tail="upper")[0]
    )


def test_quantile_ordering_and_zero_inflated_rainfall() -> None:
    climate = np.concatenate([np.zeros(80), np.linspace(1.0, 20.0, 20)])[:, None]
    values = quantiles(climate)
    assert np.all(np.diff(values[:, 0]) >= 0)
    result = extreme_forecast_index(np.zeros((51, 1)), climate)
    assert -1.0 <= result[0] <= 1.0


def test_missing_members_are_excluded_without_hiding_valid_distribution() -> None:
    climate = np.linspace(-2.0, 2.0, 101)[:, None]
    forecast = np.linspace(-1.0, 3.0, 51)[:, None]
    expected_efi = extreme_forecast_index(forecast[1:], climate[1:])
    expected_sot = shift_of_tails(forecast[1:], climate[1:], tail="upper")
    forecast[0] = np.nan
    climate[0] = np.nan
    np.testing.assert_allclose(extreme_forecast_index(forecast, climate), expected_efi)
    np.testing.assert_allclose(
        shift_of_tails(forecast, climate, tail="upper"), expected_sot
    )
    assert np.isnan(
        extreme_forecast_index(
            np.asarray([[np.nan], [1.0]]),
            np.asarray([[np.nan], [0.0]]),
        )[0]
    )


def test_complete_week_enforcement_and_precipitation_total() -> None:
    daily = np.ones((2, 42, 1))
    np.testing.assert_allclose(complete_weekly_samples(daily, aggregation="sum"), 7.0)
    daily[0, 3, 0] = np.nan
    weekly = complete_weekly_samples(daily, aggregation="sum")
    assert np.isnan(weekly[0, 0, 0])
    with np.testing.assert_raises(ValueError):
        complete_weekly_samples(np.ones((2, 41)), aggregation="mean")


def test_joint_matrix_uses_paired_valid_members_and_boundary_rule() -> None:
    rainfall = np.asarray([0.0, 1.0, 2.0, 3.0, np.nan, 3.0])
    temperature = np.asarray([0.0, 1.0, 2.0, 3.0, 3.0, np.nan])
    result = paired_tercile_matrix(rainfall, temperature, (1.0, 2.0), (1.0, 2.0))
    np.testing.assert_array_equal(result["counts"], np.diag([1, 2, 1]))
    assert result["paired_member_count"] == 4
    assert abs(float(np.asarray(result["percentages"]).sum()) - 100.0) < 1e-12
    # A marginal product would populate off-diagonal cells; paired outcomes do not.
    assert int(np.asarray(result["counts"])[0, 2]) == 0


def test_published_v3_extremes_and_joint_matrix_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    forecast = json.loads(
        (root / "public/data/forecasts/ifs/20260926.json").read_text()
    )
    regional = json.loads(
        (root / "public/data/regional/ifs/20260926.json").read_text()
    )
    assert forecast["schema_version"] == 3
    assert forecast["extreme_definition"]["climate_sample_count"] == 3060
    assert forecast["extreme_definition"]["initialization_dates"] == [
        "0922", "0926", "0929"
    ]
    for week in forecast["weeks"]:
        assert len(week["fields"]["rainfall_efi"]) == 729
        finite_efi = [value for value in week["fields"]["rainfall_efi"] if value is not None]
        assert all(-1.0 <= value <= 1.0 for value in finite_efi)
        assert set(week["extreme_samples"]["forecast_valid_member_count"]) == {100}
        assert set(week["extreme_samples"]["climate_valid_sample_count"]) == {3060}
        assert "rainfall_sot_lower" not in week["fields"]
        summary = week["distribution_summaries"]["rainfall"]
        assert summary["probabilities"] == [0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]
        assert all(len(values) == 729 for values in summary["forecast"])

    assert regional["schema_version"] == 3
    for week in regional["weeks"]:
        proxy = next(
            region for region in week["regions"]
            if region["id"] == "indo_gangetic_administrative_proxy"
        )
        matrix = proxy["joint_tercile"]
        assert matrix["paired_member_count"] == 100
        assert sum(sum(row) for row in matrix["counts"]) == 100
        assert abs(sum(sum(row) for row in matrix["percentages"]) - 100.0) < 1e-6
