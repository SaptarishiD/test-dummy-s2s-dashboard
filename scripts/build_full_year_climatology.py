#!/usr/bin/env python3
"""Build a complete India model climatology from the lossless native archive.

Extraction is resumable per initialization. Existing validated JJAS rainfall,
temperature shards and wind means are reused; all other months are read from
the completed global Zarr. Private NetCDF outputs never enter the web package.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import xarray as xr
from numcodecs import blosc

blosc.set_nthreads(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from science.zarr_v2 import _metadata, _chunk_path, _decode_chunk, read_array, read_axis0_slice
from science.calendar import native_slot, native_initialization

BASE = Path('/storage/raj.ayush/s2s_final_data/final_iteration/model-runs/fuxi')
ARCHIVE = BASE / 'native_reforecast_global_2002_2021.zarr'
SEASONAL = BASE / 'native_reforecast_jjas_2002_2021'
OUTPUT = BASE / 'native_reforecast_full_year_2002_2021'
VARIABLES = ('tp', 't2m', 'u850', 'v850')
YEARS = np.arange(2002, 2022)
DIMS = ('hindcast_year', 'init_slot', 'lead_day', 'latitude', 'longitude')


def write_nc(dataset: xr.Dataset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.nc.part')
    dataset.to_netcdf(temporary, encoding={
        name: {'zlib': True, 'complevel': 2, 'dtype': 'float32'}
        for name in dataset.data_vars if dataset[name].dtype.kind == 'f'
    })
    temporary.replace(path)


def extract(index: int, output: Path) -> None:
    attrs = json.loads((ARCHIVE / '.zattrs').read_text())
    if attrs.get('status') != 'complete':
        raise ValueError('Archive is incomplete')
    stamp = str(read_array(ARCHIVE, 'init_yyyymmdd')[index])
    print(f'starting {stamp}', flush=True)
    path = output / 'shards' / f'{stamp}.nc'
    if path.exists():
        with xr.open_dataset(path) as d:
            if d.sizes.get('member') != 51 or d.sizes.get('lead_day') != 42:
                raise ValueError(f'Incomplete existing shard: {path}')
        print(f'existing {stamp}', flush=True)
        return
    seasonal = SEASONAL / 'shards' / f'{stamp}.nc'
    if seasonal.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(seasonal)
        print(f'reused {stamp}', flush=True)
        return
    if not bool(read_axis0_slice(ARCHIVE, 'init_complete', index, index + 1)[0]):
        raise ValueError(f'Archive initialization is incomplete: {stamp}')
    values, latitude, longitude = read_native_fields(ARCHIVE, index)
    if values.shape != (51, 42, 4, 27, 27) or not np.isfinite(values).all():
        raise ValueError(f'Invalid native sample: {stamp}')
    if values[:, :, 0].min() < 0 or not 180 < values[:, :, 1].min() < values[:, :, 1].max() < 350:
        raise ValueError(f'Implausible rainfall/temperature: {stamp}')
    if np.abs(values[:, :, 2:]).max() > 150:
        raise ValueError(f'Implausible wind: {stamp}')
    coords = {
        'member': np.arange(51, dtype=np.int16),
        'lead_day': np.arange(1, 43, dtype=np.int16),
        'latitude': latitude,
        'longitude': longitude,
    }
    shard = xr.Dataset({v: (
        ('member', 'lead_day', 'latitude', 'longitude'), values[:, :, j],
        {'units': 'mm h-1' if v == 'tp' else 'K' if v == 't2m' else 'm s-1'}
    ) for j, v in enumerate(VARIABLES)}, coords=coords, attrs={
        'source': str(ARCHIVE), 'initialization': stamp,
        'source_archive_records_sha256': attrs['archive_records_sha256'],
        'source_member_count': 51,
    })
    write_nc(shard, path)
    print(f'extracted {stamp}', flush=True)


def read_native_fields(archive: Path, index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decode only the four required channel groups, cropping each immediately."""
    latitude = read_array(archive, 'lat')
    longitude = read_array(archive, 'lon')
    lat_indices = np.flatnonzero((latitude <= 39) & (latitude >= 0))
    lon_indices = np.flatnonzero((longitude >= 60) & (longitude <= 99))
    if len(lat_indices) != 27 or len(lon_indices) != 27:
        raise ValueError('Native India grid is incomplete')
    lat_slice = slice(int(lat_indices[0]), int(lat_indices[-1]) + 1)
    lon_slice = slice(int(lon_indices[0]), int(lon_indices[-1]) + 1)
    channels = read_array(archive, 'channel').astype(str).tolist()
    meta = _metadata(archive, 'forecast')
    if meta.shape != (2080, 51, 42, 26, 121, 240) or meta.chunks != (1, 51, 7, 4, 121, 240):
        raise ValueError('Native archive shape/chunks differ from validated contract')
    output = np.empty((51, 42, 4, 27, 27), dtype='float32')
    groups = {}
    for destination, name in enumerate(VARIABLES):
        channel = channels.index(name)
        groups.setdefault(channel // 4, []).append((destination, channel % 4))
    for week in range(6):
        for group, requested in groups.items():
            coordinates = (index, 0, week, group, 0, 0)
            key = _chunk_path(meta, coordinates)
            if not key.is_file():
                raise ValueError(f'Missing completed archive chunk: {key}')
            edge = (1, 51, 7, min(4, 26 - group * 4), 121, 240)
            block = _decode_chunk(key.read_bytes(), meta, full_shape=meta.chunks, edge_shape=edge, key=key)
            for destination, channel in requested:
                output[:, week * 7:(week + 1) * 7, destination] = block[0, :, :, channel, lat_slice, lon_slice]
            del block
    return output, latitude[lat_slice].astype('float32'), longitude[lon_slice].astype('float32')


def summarize(yearly: np.ndarray, units: str) -> dict[str, tuple]:
    """Use identical yearly weighting and LOYO definition to the JJAS baseline."""
    return {
        'ensemble_mean': (DIMS, yearly, {'units': units}),
        'model_climatology_mean': (DIMS[1:], yearly.mean(axis=0), {'units': units}),
        'model_climatology_std': (DIMS[1:], yearly.std(axis=0, ddof=1), {'units': units}),
        'model_climatology_p10': (DIMS[1:], np.quantile(yearly, .1, axis=0), {'units': units}),
        'model_climatology_p90': (DIMS[1:], np.quantile(yearly, .9, axis=0), {'units': units}),
        'model_climatology_loyo': (DIMS, (yearly.sum(axis=0) - yearly) / 19, {'units': units}),
    }


def combine(output: Path) -> None:
    stamps = read_array(ARCHIVE, 'init_yyyymmdd').astype(str).tolist()
    attrs = json.loads((ARCHIVE / '.zattrs').read_text())
    slots = sorted({native_slot(s) for s in stamps})
    expected = {native_initialization(year, slot) for year in YEARS for slot in slots}
    if set(stamps) != expected or len(slots) != 104:
        raise ValueError('Expected all 104 slots in each of the 20 years')
    missing = [s for s in stamps if not (output / 'shards' / f'{s}.nc').is_file()]
    if missing:
        raise ValueError(f'Missing {len(missing)} shards, including {missing[:5]}')
    values = {v: np.empty((20, 104, 42, 27, 27), dtype='float32') for v in VARIABLES}
    with xr.open_dataset(SEASONAL / 'fuxi_s2s_jjas_model_climatology_2002_2021_loyo.nc') as rain_climate, xr.open_dataset(SEASONAL / 'fuxi_s2s_wind850_climatology_jjas_allslots_2002_2021.nc') as wind_climate:
        seasonal_slots = set(rain_climate.init_slot.values.astype(str))
        for yi, year in enumerate(YEARS):
            for si, slot in enumerate(slots):
                if slot in seasonal_slots:
                    for v in VARIABLES:
                        source = rain_climate if v in ('tp', 't2m') else wind_climate
                        values[v][yi, si] = source[f'{v}_ensemble_mean'].sel(hindcast_year=year, init_slot=slot).values
                else:
                    stamp = native_initialization(year, slot)
                    with xr.open_dataset(output / 'shards' / f'{stamp}.nc') as d:
                        for v in VARIABLES:
                            mean = d[v].mean('member').values
                            values[v][yi, si] = mean * 24 if v == 'tp' else mean
                print(f'combined {year}{slot}', flush=True)
    for v, a in values.items():
        if not np.isfinite(a).all():
            raise ValueError(f'Incomplete {v} climatology')
    coords = {'hindcast_year': YEARS, 'init_slot': slots,
              'lead_day': np.arange(1, 43, dtype=np.int16),
              'latitude': np.linspace(39, 0, 27, dtype='float32'),
              'longitude': np.linspace(60, 99, 27, dtype='float32')}
    common_attrs = {
        'title': 'FuXi-S2S full-year 2002-2021 native model climatology',
        'calendar_scope': 'full_year', 'source_member_count': 51,
        'source_archive_records_sha256': attrs['archive_records_sha256'],
        'climatology_definition': 'One 51-member mean per year; 20 years equally weighted',
        'loyo_definition': 'Mean of the other 19 years at the same slot and lead',
        'seasonal_overlap': 'JJAS yearly means copied unchanged from validated seasonal baseline',
        'february_alignment': 'Slot 0228 is the native last-day-of-February start: 0229 in leap years, 0228 otherwise; actual source dates are retained.',
    }
    variables = {}
    for v in ('tp', 't2m'):
        for suffix, definition in summarize(values[v], 'mm day-1' if v == 'tp' else 'K').items():
            variables[f'{v}_{suffix}'] = definition
    variables['hindcast_sample_count'] = (('init_slot', 'lead_day'), np.full((104, 42), 20, dtype='int16'))
    variables['source_initialization'] = (('hindcast_year', 'init_slot'), np.asarray([
        [native_initialization(year, slot) for slot in slots] for year in YEARS
    ]))
    write_nc(xr.Dataset(variables, coords=coords, attrs=common_attrs),
             output / 'fuxi_s2s_full_year_model_climatology_2002_2021_loyo.nc')
    wind = {}
    wind['source_initialization'] = variables['source_initialization']
    for v in ('u850', 'v850'):
        wind[f'{v}_ensemble_mean'] = (DIMS, values[v], {'units': 'm s-1'})
        wind[f'{v}_model_climatology_mean'] = (DIMS[1:], values[v].mean(axis=0), {'units': 'm s-1'})
    write_nc(xr.Dataset(wind, coords=coords, attrs=common_attrs),
             output / 'fuxi_s2s_full_year_wind850_climatology_2002_2021.nc')
    print(json.dumps({'status': 'complete', 'slots': 104, 'years': 20, 'members': 51, 'output': str(output)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('extract', 'combine'))
    parser.add_argument('--index', type=int)
    parser.add_argument('--slot-index', type=int, help='Extract all 20 years of one native calendar slot')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.command == 'extract':
        if args.slot_index is not None:
            stamps = read_array(ARCHIVE, 'init_yyyymmdd').astype(str).tolist()
            slots = sorted({s[4:] for s in stamps})
            slot = slots[args.slot_index]
            for index, stamp in enumerate(stamps):
                if stamp[4:] == slot:
                    extract(index, args.output)
        elif args.index is None or not 0 <= args.index < 2080:
            raise ValueError('Extraction requires an archive index in 0..2079')
        else:
            extract(args.index, args.output)
    else:
        combine(args.output)


if __name__ == '__main__':
    main()
