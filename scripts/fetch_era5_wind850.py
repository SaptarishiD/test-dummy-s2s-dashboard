#!/usr/bin/env python3
"""Extract ERA5 850 hPa U/V samples for an ERA5-baseline wind anomaly.

Reads the public WeatherBench2 ERA5 archive (1.5-degree conservative regrid,
6-hourly, 1959 to 2023-01-10) straight from Google Cloud Storage and keeps,
for each requested year, the 42 days x 4 synoptic times starting on the
initialization calendar day over a 1.5-degree sub-domain.  The output feeds
``scripts/import_external_issue.py --wind850-climatology``.

Only stdlib networking plus numcodecs/numpy are needed; no zarr install.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
from numcodecs import Blosc

BASE = (
    "https://storage.googleapis.com/weatherbench2/datasets/era5/"
    "1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr"
)
SOURCE = "WeatherBench2 ERA5 1.5-degree conservative, 6-hourly (Google Cloud public dataset)"
STEPS = 42 * 4
CHUNK_T = 8
LEVELS = 13
codec = Blosc()


def get(path: str) -> bytes:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(f"{BASE}/{path}", timeout=120) as response:
                return response.read()
        except OSError:
            if attempt == 4:
                raise
    raise AssertionError("unreachable")


def coordinate(name: str, dtype: str) -> np.ndarray:
    return np.frombuffer(codec.decode(get(f"{name}/0")), dtype=dtype)


def step_index(moment: datetime) -> int:
    return int((moment - datetime(1959, 1, 1)).total_seconds() // 21600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-mmdd", required=True, help="Initialization calendar day, e.g. 1028")
    parser.add_argument("--first-year", type=int, default=2011)
    parser.add_argument("--last-year", type=int, default=2022)
    parser.add_argument("--south", type=float, default=6.0)
    parser.add_argument("--north", type=float, default=39.0)
    parser.add_argument("--west", type=float, default=66.0)
    parser.add_argument("--east", type=float, default=99.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    level = coordinate("level", "<i8")
    latitude = coordinate("latitude", "<f8")
    longitude = coordinate("longitude", "<f8")
    time = coordinate("time", "<i8")
    if time[0] != 0 or time[1] != 6:
        raise ValueError("unexpected WeatherBench2 time axis")
    level_index = int(np.flatnonzero(level == 850)[0])
    lat_index = np.flatnonzero(
        (latitude >= args.south - 0.1) & (latitude <= args.north + 0.1)
    )
    lon_index = np.flatnonzero(
        (longitude >= args.west - 0.1) & (longitude <= args.east + 0.1)
    )
    years = list(range(args.first_year, args.last_year + 1))
    month, day = int(args.start_mmdd[:2]), int(args.start_mmdd[2:])
    starts = {year: step_index(datetime(year, month, day)) for year in years}
    if max(starts.values()) + STEPS > time.size:
        raise ValueError("requested years run past the end of the archive")

    def chunk(job: tuple[str, int]) -> np.ndarray:
        variable, chunk_id = job
        raw = codec.decode(get(f"{variable}/{chunk_id}.0.0.0"))
        block = np.frombuffer(raw, dtype="<f4").reshape(CHUNK_T, LEVELS, 240, 121)
        # (time, longitude, latitude) -> (time, latitude, longitude)
        return block[:, level_index][:, lon_index][:, :, lat_index].transpose(0, 2, 1)

    jobs = [
        (variable, chunk_id)
        for start in starts.values()
        for chunk_id in range(start // CHUNK_T, (start + STEPS - 1) // CHUNK_T + 1)
        for variable in ("u_component_of_wind", "v_component_of_wind")
    ]
    with ThreadPoolExecutor(24) as pool:
        blocks = dict(zip(jobs, pool.map(chunk, jobs)))

    order = np.argsort(-latitude[lat_index])  # north-to-south like the forecast grid
    samples = {}
    for year, start in starts.items():
        for variable, key in (("u_component_of_wind", "u"), ("v_component_of_wind", "v")):
            series = np.stack([
                blocks[(variable, step // CHUNK_T)][step % CHUNK_T]
                for step in range(start, start + STEPS)
            ])
            samples[f"{key}_{year}"] = series[:, order]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        latitude=latitude[lat_index][order],
        longitude=longitude[lon_index],
        years=np.asarray(years),
        start_mmdd=np.asarray(args.start_mmdd),
        source=np.asarray(SOURCE),
        **samples,
    )
    print(json.dumps({"chunks": len(jobs), "years": [years[0], years[-1]], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
