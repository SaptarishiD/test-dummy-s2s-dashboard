"""ECMWF-style ensemble extreme diagnostics.

The functions in this module operate on complete member samples.  They do not
interpret EFI or SOT as probabilities or skill scores; both diagnostics are
relative to the supplied model-climate distribution.
"""

from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import ArrayLike, NDArray


PERCENTILE_LEVELS = np.linspace(0.0, 1.0, 101, dtype=np.float64)
PUBLIC_PERCENTILE_LEVELS = np.asarray(
    [0.01, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99], dtype=np.float64
)


def _as_member_samples(values: ArrayLike, *, name: str) -> NDArray[np.float64]:
    samples = np.asarray(values, dtype=np.float64)
    if samples.ndim < 1:
        raise ValueError(f"{name} must have a member/sample dimension")
    if samples.shape[0] < 2:
        raise ValueError(f"{name} requires at least two samples")
    return samples


def quantiles(
    values: ArrayLike,
    probabilities: ArrayLike = PERCENTILE_LEVELS,
) -> NDArray[np.float64]:
    """Return linear quantiles along the leading sample dimension."""

    samples = _as_member_samples(values, name="values")
    levels = np.asarray(probabilities, dtype=np.float64)
    if levels.ndim != 1 or np.any((levels < 0.0) | (levels > 1.0)):
        raise ValueError("quantile probabilities must be one-dimensional in [0, 1]")
    valid_count = np.sum(np.isfinite(samples), axis=0)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        result = np.nanquantile(samples, levels, axis=0, method="linear")
    return np.where(valid_count >= 2, result, np.nan)


def extreme_forecast_index(
    forecast_members: ArrayLike,
    climate_samples: ArrayLike,
) -> NDArray[np.float64]:
    """Compute EFI using ECMWF's analytic 101-quantile integration.

    The implementation follows the public Earthkit algorithm: the climate is
    represented by its 0--100 percentiles, the fraction of forecast members at
    or below each percentile is evaluated, and the tail-weighted integral is
    calculated analytically between adjacent percentile levels.
    """

    forecast = _as_member_samples(forecast_members, name="forecast_members")
    climate = _as_member_samples(climate_samples, name="climate_samples")
    if forecast.shape[1:] != climate.shape[1:]:
        raise ValueError("forecast and climate point dimensions must match")

    climate_percentiles = quantiles(climate)
    forecast_valid = np.isfinite(forecast)
    forecast_count = np.sum(forecast_valid, axis=0)
    climate_count = np.sum(np.isfinite(climate), axis=0)
    missing = (forecast_count < 2) | (climate_count < 2) | np.any(
        ~np.isfinite(climate_percentiles), axis=0
    )
    forecast_cdf = np.full(climate_percentiles.shape, np.nan, dtype=np.float64)
    np.divide(
        np.sum(
            forecast_valid[np.newaxis, ...]
            & (forecast[np.newaxis, ...] <= climate_percentiles[:, np.newaxis, ...]),
            axis=1,
        ),
        forecast_count,
        out=forecast_cdf,
        where=forecast_count >= 2,
    )

    probability = PERCENTILE_LEVELS
    cdf_derivative = np.diff(forecast_cdf, axis=0) * 100.0
    acos_difference = np.diff(np.arccos(np.sqrt(probability)))
    product_difference = np.diff(np.sqrt(probability * (1.0 - probability)))
    coefficient = (
        (1.0 - 2.0 * probability[:-1]) * acos_difference
        + product_difference
    )
    reshape = (100,) + (1,) * (forecast.ndim - 1)
    result = np.sum(
        (2.0 * forecast_cdf[:-1] - 1.0)
        * acos_difference.reshape(reshape)
        + coefficient.reshape(reshape) * cdf_derivative
        - product_difference.reshape(reshape),
        axis=0,
    )
    result *= 2.0 / np.pi
    result = np.clip(result, -1.0, 1.0)
    return np.where(missing, np.nan, result)


def shift_of_tails(
    forecast_members: ArrayLike,
    climate_samples: ArrayLike,
    *,
    tail: str,
    denominator_tolerance: float = 1e-12,
) -> NDArray[np.float64]:
    """Compute upper (90/99) or lower (10/1) Shift of Tails.

    Values are deliberately not clipped.  A non-finite or effectively zero
    climate-tail denominator is returned as NaN so missing/degenerate values
    cannot be confused with an ordinary near-zero SOT.
    """

    forecast = _as_member_samples(forecast_members, name="forecast_members")
    climate = _as_member_samples(climate_samples, name="climate_samples")
    if forecast.shape[1:] != climate.shape[1:]:
        raise ValueError("forecast and climate point dimensions must match")
    if tail == "upper":
        forecast_quantile = quantiles(forecast, [0.90])[0]
        climate_near, climate_tail = quantiles(climate, [0.90, 0.99])
    elif tail == "lower":
        forecast_quantile = quantiles(forecast, [0.10])[0]
        climate_near, climate_tail = quantiles(climate, [0.10, 0.01])
    else:
        raise ValueError("tail must be 'upper' or 'lower'")

    denominator = climate_tail - climate_near
    valid = (
        np.isfinite(forecast_quantile)
        & np.isfinite(climate_tail)
        & np.isfinite(denominator)
        & (np.abs(denominator) > denominator_tolerance)
    )
    result = np.full(denominator.shape, np.nan, dtype=np.float64)
    np.divide(
        forecast_quantile - climate_tail,
        denominator,
        out=result,
        where=valid,
    )
    return result


def complete_weekly_samples(
    daily_values: ArrayLike,
    *,
    aggregation: str,
) -> NDArray[np.float64]:
    """Aggregate 42 complete daily member values into six forecast weeks."""

    daily = np.asarray(daily_values, dtype=np.float64)
    if daily.ndim < 2 or daily.shape[1] != 42:
        raise ValueError("weekly aggregation requires exactly 42 lead days")
    reshaped = daily.reshape(daily.shape[0], 6, 7, *daily.shape[2:])
    finite = np.all(np.isfinite(reshaped), axis=2)
    if aggregation == "sum":
        weekly = np.sum(reshaped, axis=2)
    elif aggregation == "mean":
        weekly = np.mean(reshaped, axis=2)
    else:
        raise ValueError("aggregation must be 'sum' or 'mean'")
    return np.where(finite, weekly, np.nan)


def paired_tercile_matrix(
    rainfall_members: ArrayLike,
    temperature_members: ArrayLike,
    rainfall_thresholds: tuple[float, float],
    temperature_thresholds: tuple[float, float],
) -> dict[str, object]:
    """Return a 3x3 matrix from paired members using exclusive tercile bins."""

    rainfall = np.asarray(rainfall_members, dtype=np.float64)
    temperature = np.asarray(temperature_members, dtype=np.float64)
    if rainfall.ndim != 1 or temperature.ndim != 1 or rainfall.shape != temperature.shape:
        raise ValueError("paired rainfall and temperature members must be equal 1-D arrays")
    valid = np.isfinite(rainfall) & np.isfinite(temperature)
    paired_count = int(valid.sum())
    if paired_count == 0:
        raise ValueError("joint matrix requires at least one valid member pair")

    rain_lower, rain_upper = rainfall_thresholds
    temp_lower, temp_upper = temperature_thresholds
    if rain_lower > rain_upper or temp_lower > temp_upper:
        raise ValueError("tercile thresholds must be ordered")
    # Existing dashboard rule: equality belongs to the mutually exclusive near bin.
    rain_category = np.where(
        rainfall[valid] < rain_lower,
        0,
        np.where(rainfall[valid] > rain_upper, 2, 1),
    )
    temp_category = np.where(
        temperature[valid] < temp_lower,
        0,
        np.where(temperature[valid] > temp_upper, 2, 1),
    )
    counts = np.zeros((3, 3), dtype=np.int64)
    np.add.at(counts, (temp_category, rain_category), 1)
    percentages = counts.astype(np.float64) * 100.0 / paired_count
    return {
        "paired_member_count": paired_count,
        "counts": counts,
        "percentages": percentages,
    }
