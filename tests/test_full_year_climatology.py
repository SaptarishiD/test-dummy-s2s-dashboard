"""Full-year climate weighting, annual wrap, and seasonal fallback boundaries."""
import numpy as np
import pytest

from science.calendar import calendar_bracket, native_slot, native_initialization
from scripts.build_full_year_climatology import summarize


@pytest.mark.parametrize(("target", "expected"), [
    ("0101", ("1229", "0103", 3 / 5)),
    ("1231", ("1229", "0103", 2 / 5)),
    ("0103", ("0103", "0103", 0.0)),
])
def test_full_year_calendar_wrap(target, expected):
    assert calendar_bracket(["0103", "1229"], target, cyclic=True) == expected


def test_seasonal_calendar_cannot_wrap_across_uncovered_months():
    with pytest.raises(ValueError, match="outside"):
        calendar_bracket(["0602", "0929"], "1003")


def test_february_29_uses_calendar_interpolation():
    assert calendar_bracket(["0228", "0303"], "0229", cyclic=True) == ("0228", "0303", .25)


def test_equal_year_weighting_and_leave_one_year_out():
    yearly = np.arange(20, dtype='float32').reshape(20, 1, 1, 1, 1)
    result = summarize(yearly, 'K')
    np.testing.assert_allclose(result['model_climatology_mean'][1], 9.5)
    np.testing.assert_allclose(result['model_climatology_loyo'][1][0], 10.)
    np.testing.assert_allclose(result['model_climatology_loyo'][1][-1], 9.)
    np.testing.assert_allclose(result['model_climatology_std'][1], np.sqrt(35.))


def test_end_of_february_has_one_actual_start_per_year():
    years = range(2002, 2022)
    stamps = [native_initialization(year, '0228') for year in years]
    assert len(stamps) == 20
    assert sum(stamp.endswith('0229') for stamp in stamps) == 5
    assert {native_slot(stamp) for stamp in stamps} == {'0228'}
    assert native_initialization(2020, '1003') == '20201003'


@pytest.mark.parametrize(('year', 'target', 'expected'), [
    (2028, '0229', ('0228', '0228', 0.0)),
    (2028, '0228', ('0224', '0228', .8)),
    (2028, '0301', ('0228', '0303', 1 / 3)),
    (2026, '0228', ('0228', '0228', 0.0)),
    (2026, '0301', ('0228', '0303', 1 / 3)),
    (2026, '0101', ('1229', '0103', 3 / 5)),
])
def test_native_calendar_uses_forecast_year(year, target, expected):
    assert calendar_bracket(['0103', '0224', '0228', '0303', '1229'], target,
                            cyclic=True, year=year, native_february=True) == expected
