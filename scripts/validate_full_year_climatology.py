#!/usr/bin/env python3
"""Validate full-year climatology against seasonal and independent native data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr
from netCDF4 import Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.build_full_year_climatology import BASE, OUTPUT, SEASONAL, YEARS
from science.validators import sha256_file, validate_fuxi_climatology
from science.calendar import full_year_slots, native_initialization


def validate(output: Path) -> dict:
    model_path = output / 'fuxi_s2s_full_year_model_climatology_2002_2021_loyo.nc'
    wind_path = output / 'fuxi_s2s_full_year_wind850_climatology_2002_2021.nc'
    hashes = {'model': sha256_file(model_path), 'wind': sha256_file(wind_path)}
    validate_fuxi_climatology(model_path, hashes['model'])
    native = Path('/storage/raj.ayush/archive/All_Model_Data/models/fuxi/clima')
    checks = {}
    with xr.open_dataset(model_path) as model, xr.open_dataset(wind_path) as wind, xr.open_dataset(SEASONAL / 'fuxi_s2s_jjas_model_climatology_2002_2021_loyo.nc') as seasonal, xr.open_dataset(SEASONAL / 'fuxi_s2s_wind850_climatology_jjas_allslots_2002_2021.nc') as seasonal_wind:
        for d in (model, wind):
            if not full_year_slots(d.init_slot.values) or d.hindcast_year.values.tolist() != YEARS.tolist():
                raise ValueError('Baseline lacks 104 slots or exact 2002-2021 years')
            np.testing.assert_array_equal(d.lead_day.values, np.arange(1, 43))
            np.testing.assert_array_equal(d.source_initialization.values, np.asarray([
                [native_initialization(year, slot) for slot in d.init_slot.values]
                for year in YEARS
            ]))
        for v in ('tp', 't2m', 'u850', 'v850'):
            d = model if v in ('tp', 't2m') else wind
            old = seasonal if v in ('tp', 't2m') else seasonal_wind
            yearly = d[f'{v}_ensemble_mean'].transpose('hindcast_year','init_slot','lead_day','latitude','longitude').values
            if not np.isfinite(yearly).all():
                raise ValueError(f'Incomplete yearly data: {v}')
            np.testing.assert_allclose(d[f'{v}_model_climatology_mean'].values, yearly.mean(axis=0), rtol=0, atol=1e-5)
            if v in ('tp','t2m'):
                loyo = d[f'{v}_model_climatology_loyo'].transpose('hindcast_year','init_slot','lead_day','latitude','longitude').values
                np.testing.assert_allclose(loyo, (yearly.sum(axis=0) - yearly) / 19, rtol=0, atol=1e-5)
            overlap = d[f'{v}_ensemble_mean'].sel(init_slot=old.init_slot).transpose('hindcast_year','init_slot','lead_day','latitude','longitude').values
            previous = old[f'{v}_ensemble_mean'].transpose('hindcast_year','init_slot','lead_day','latitude','longitude').values
            np.testing.assert_array_equal(overlap, previous)
            checks[v] = {'full_year_finite': True, 'seasonal_yearly_means_identical': True}
        # The legacy January file is mislabeled: its mean matches five years.
        # Retain this finding and verify January against original native members.
        for v in ('tp', 't2m'):
            with xr.open_dataset(native / f'{v}_clima_0103.nc', decode_times=False) as independent:
                mean = independent[f'{v}_mean'].sel(lat=slice(39,0), lon=slice(60,99)).values
                if v == 'tp':
                    mean = mean * 24
                actual = model[f'{v}_model_climatology_mean'].sel(init_slot='0103').values
                try:
                    np.testing.assert_allclose(actual, mean, rtol=1e-5, atol=5e-4)
                    checks[f'{v}_0103_precomputed_reference'] = {'status': 'agrees'}
                except AssertionError:
                    subset = model[f'{v}_ensemble_mean'].sel(init_slot='0103', hindcast_year=[2002,2017,2018,2019,2020]).mean('hindcast_year').values
                    np.testing.assert_allclose(subset, mean, rtol=1e-5, atol=5e-4)
                    checks[f'{v}_0103_precomputed_reference'] = {
                        'status': 'rejected', 'reason': 'Claims 20 years but matches only five yearly means',
                        'matching_years': [2002,2017,2018,2019,2020],
                        'maximum_difference_from_full_twenty_year_mean': float(np.abs(actual-mean).max()),
                    }
        native_sums = {v: np.zeros((27,27), dtype='float64') for v in ('tp','t2m','u850','v850')}
        original = Path('/storage/raj.ayush/archive/All_Model_Data/models/fuxi/extracted_full')
        for year in YEARS:
            for member in range(51):
                path = original / str(year) / '01' / f'{year}0103' / 'member' / f'{member:02d}' / '01.nc'
                with Dataset(path) as source:
                    source.set_auto_mask(False)
                    channels = source.variables['channel'][:].astype(str).tolist()
                    np.testing.assert_array_equal(source.variables['lat'][34:61], model.latitude.values)
                    np.testing.assert_array_equal(source.variables['lon'][40:67], model.longitude.values)
                    field = source.variables['__xarray_dataarray_variable__']
                    for v in native_sums:
                        values = np.asarray(field[0,0,channels.index(v),34:61,40:67], dtype='float64')
                        if not np.isfinite(values).all():
                            raise ValueError(f'Original native member contains missing {v}: {year}/{member}')
                        native_sums[v] += values
            print(f'Original January members checked: {year}, all 51 members', flush=True)
        for v, total in native_sums.items():
            d = model if v in ('tp','t2m') else wind
            direct_mean = total / (20 * 51) * (24 if v == 'tp' else 1)
            actual = d[f'{v}_model_climatology_mean'].sel(init_slot='0103', lead_day=1).values
            np.testing.assert_allclose(actual, direct_mean, rtol=1e-5, atol=5e-4)
            checks[f'{v}_0103_original_1020_members_day1_max_difference'] = float(np.abs(actual-direct_mean).max())
        for slot in ('1003', '1229'):
            for v in ('tp','t2m'):
                with xr.open_dataset(native / f'{v}_clima_{slot}.nc', decode_times=False) as independent:
                    mean = independent[f'{v}_mean'].sel(lat=slice(39,0),lon=slice(60,99)).values
                    if v == 'tp':
                        mean = mean * 24
                    actual = model[f'{v}_model_climatology_mean'].sel(init_slot=slot).values
                    np.testing.assert_allclose(actual, mean, rtol=1e-5, atol=5e-4)
                    checks[f'{v}_{slot}_independent_mean_max_difference'] = float(np.abs(actual - mean).max())
    result = {'status': 'validated', 'slots': 104, 'years': 20, 'members_per_year': 51, 'sha256': hashes, 'checks': checks}
    (output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    print(json.dumps(validate(parser.parse_args().output), indent=2))
