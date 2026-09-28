"""Synthetic contract tests for the member-derived summary package."""

from __future__ import annotations

import numpy as np

from scripts.build_regional_outlook import (
    nullable_values,
    probability_record,
    serialize_grid_summary,
    variable_grid_fields,
)


def test_grid_summary_preserves_exact_ties_and_degenerate_reference_masks() -> None:
    forecast = np.asarray(
        [
            [[[[0.0, 5.0]]]],
            [[[[1.0, 5.0]]]],
            [[[[3.0, 5.0]]]],
        ]
    ).reshape(3, 1, 1, 2)
    history = np.asarray(
        [
            [[[[0.0, 0.0]]]],
            [[[[1.0, 0.0]]]],
            [[[[2.0, 0.0]]]],
            [[[[3.0, 0.0]]]],
        ]
    ).reshape(4, 1, 1, 2)

    probabilities, summary = variable_grid_fields(
        forecast,
        history,
        minimum_valid_members=3,
        units="mm day⁻¹",
    )

    assert summary["valid_member_count"].tolist() == [[[3.0, 3.0]]]
    assert summary["leading_category"].tolist() == [[["mixed", None]]]
    assert summary["tercile_available"].tolist() == [[[True, False]]]
    assert sum(
        probabilities[category][0, 0, 0]
        for category in ("below_normal", "near_normal", "above_normal")
    ) == 100.0
    assert all(
        np.isnan(probabilities[category][0, 0, 1])
        for category in ("below_normal", "near_normal", "above_normal")
    )

    serialized = serialize_grid_summary(summary, 0)
    assert serialized["leading_category"] == ["mixed", None]
    assert serialized["tercile_available"] == [True, False]
    assert serialized["valid_member_count"] == [3, 3]
    assert nullable_values(probabilities["below_normal"][0]) == [33.33, None]


def test_grid_summary_quantiles_are_member_derived_and_ordered() -> None:
    forecast = np.arange(5.0).reshape(5, 1, 1, 1)
    history = np.arange(20.0).reshape(20, 1, 1, 1)
    _, summary = variable_grid_fields(
        forecast,
        history,
        minimum_valid_members=5,
        units="°C",
    )

    values = [
        float(summary[name][0, 0, 0])
        for name in ("p10", "p25", "p50", "p75", "p90")
    ]
    assert values == sorted(values)
    assert summary["mean"][0, 0, 0] == 2.0
    assert summary["p90_minus_p10"][0, 0, 0] == (
        summary["p90"][0, 0, 0] - summary["p10"][0, 0, 0]
    )


def test_regional_probability_rounding_preserves_exact_total() -> None:
    record = probability_record(
        {
            "below_normal": np.asarray(100.0 / 3.0),
            "near_normal": np.asarray(100.0 / 3.0),
            "above_normal": np.asarray(100.0 / 3.0),
        }
    )
    assert sum(record[name] for name in (
        "below_normal", "near_normal", "above_normal"
    )) == 100
    assert record["dominant_category"] == "mixed"
