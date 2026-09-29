# S2S Research India

A static, source-aware India subseasonal research forecast interface with a
separate dated Global Demo. India is the default page. It separates
main experimental IFS initializations, secondary near-real-time GFS-proxy
initializations, and delayed ERA5 references, exposes the available issue dates
and ensemble sizes, and provides compact issue-level downloads.
The landing forecast is the latest validated 100-member IFS issue. Selecting
GFS or ERA5 opens that source's independently dated latest validated issue.

The dated Global Demo animates a pinned 28 July 2026 set of 42 daily
ensemble-mean fields for
precipitation, 2 m temperature, 500 hPa geopotential height, 850 hPa wind,
mean sea-level pressure, sea-surface temperature, outgoing longwave radiation,
and total-column water vapour.
The site publishes compact ensemble-derived fields only. It does not contain
raw model inputs, member fields, observations, reforecasts, model weights,
credentials, or cluster paths.

## Scientific status

Each forecast package records its initialization-source family explicitly:

- **IFS operational initialization** is the main experimental guidance, built
  from ECMWF Open Data. IFS skin temperature over ocean is used as the
  disclosed SST proxy.
- **GFS operational proxy** is the secondary near-real-time source. It uses
  daily proxy fields for experimental guidance. The model was trained with
  ERA5-style inputs, and no matched GFS-initialized hindcast calibration exists
  yet.
- **ERA5 reanalysis reference** uses scientifically matched but delayed inputs
  for reference experiments and initialization-sensitivity comparisons. It is
  not a near-real-time forecast.
The 22 July 2026 issue is available from both sources with 100 members, giving
one controlled comparison in which the source is changed without changing the
initialization date. All displayed products remain experimental research
guidance, not an operational weather forecast or warning.

The global animation is an independently sampled 100-member companion ensemble
generated from the same frozen input as the earlier India case. The raw members
behind the India export had already been removed, so its exact stochastic draws
could not be reused.

The public interface uses the neutral identity **S2S Research · Experimental
Subseasonal Forecasting**. Model identity and scientific provenance remain in
this repository.

The downloadable PDF masthead uses unmodified Ashoka University and Safexpress
Centre marks sourced from the official SCDLDS website. These institutional
brand assets are stored under `scripts/assets/`, remain the property of their
respective owners, and are not covered by any source-code licence for this
prototype. The web interface itself retains the neutral S2S Research identity.

The India anomalies use a calendar-interpolated, lead-matched 2002–2021 model
native reforecast climatology. They are not IMD or IMERG anomalies. The
validated native climatology currently covers JJAS initialization slots.
Outside that window, year-round automation publishes only raw weekly rainfall
and mean temperature; anomalies and regional probabilities are withheld. The
India climatology does not extend beyond its 27 × 27 grid. The global viewer
uses a separate exact-28-July, lead-matched 2002–2021
model climatology for
precipitation, 2 m temperature, and Z500 anomalies on the full global grid.

The 6 August 2026 ERA5 issue and 15 August 2026 IFS issue also publish weekly
850 hPa wind anomalies. Shading is the signed wind-speed departure; arrows are
the U/V component departure. Both use model-state calendar interpolation with
one 51-member mean per year and equal weighting across 2002–2021. The ERA5
issue uses the native 4/8 August slots and five forecast members; the IFS issue
uses the native 11/15 August slots and all 100 forecast members. The wind layer
is shown for Weeks 1–4 by default and is included as page five of each PDF.

## Rebuild and validate

From this directory:

```bash
python scripts/validate_sources.py
python scripts/build_prototype_data.py
python scripts/build_forecast_pdfs.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
python scripts/validate_web_data.py
npm ci
npm run build
```

`validate_sources.py` reads the private scientific inputs at their configured
locations but writes only public-safe metadata. Paths can be overridden with
command-line arguments. `build_prototype_data.py` refuses source failures.
`validate_web_data.py` performs schema, finite-number, leakage, checksum, and
independent legacy-builder comparisons.

Run locally with:

```bash
npm run dev
```

### Probabilistic summary package

For a validated 100-member issue with a compatible model climatology, generate
the compact map and selected-location summaries with:

```bash
python scripts/build_regional_outlook.py \
  --forecast /private/path/to/completed-forecast.nc \
  --public-forecast public/data/forecasts/ifs/YYYYMMDD.json \
  --climatology /private/path/to/fuxi_s2s_jjas_model_climatology_2002_2021_loyo.nc \
  --minimum-valid-members 100 \
  --output public/data/regional/ifs/YYYYMMDD.json
npm run dev
```

The exporter aggregates each member into a complete seven-day week before it
calculates the mean, P10, P25, median, P75, P90, P90 - P10, valid-member count,
and tercile fractions. A partial member-week remains missing. The default
completeness threshold requires all 100 expected members and is configurable by
CLI for explicitly reviewed degraded-data workflows.

The tercile thresholds are lead-matched 1/3 and 2/3 quantiles from 20 equally
weighted yearly native-model ensemble means (2002-2021), using the existing
calendar-alignment pipeline. The probabilities are raw fractions of valid
forecast members, not calibrated event frequencies. Boundaries are mutually
exclusive: below is `X < q33`, near is `q33 <= X <= q67`, and above is
`X > q67`. Cells with repeated/non-increasing thresholds are published as
unavailable rather than forced into three categories.

Regional schema v2 carries only compact member-derived summaries; full spatial
member fields and reforecasts remain private. Older schema-v1 packages continue
to show their real tercile probabilities, while quantiles and spread display an
explicit unavailable state until that issue is regenerated.

### Extreme forecast products

IFS 26 September 2026 is the first schema-v3 extreme package. EFI and Shift of
Tails compare each complete weekly 100-member forecast distribution with the
native 2002–2021 FuXi model climate. The builder automatically selects the
three native initialization calendar dates within ±4 days of an IFS issue; for
26 September those are 22, 26, and 29 September, providing 3,060 reference
samples per grid cell and lead week. Rainfall is accumulated as a seven-day
total before comparison; temperature is averaged over the same complete week.
Only derived fields and seven compact forecast/model-climate quantiles are
public—member arrays remain private.

Rebuild the regional v2 base and then layer the v3 products with:

```bash
python scripts/build_regional_outlook.py \
  --forecast /private/path/to/20260926.nc \
  --public-forecast public/data/forecasts/ifs/20260926.json \
  --minimum-valid-members 100 \
  --output public/data/regional/ifs/20260926.json
python scripts/build_extreme_products.py \
  --forecast /private/path/to/20260926.nc \
  --public-forecast public/data/forecasts/ifs/20260926.json \
  --regional public/data/regional/ifs/20260926.json
```

EFI and SOT are raw, model-relative ensemble indices. They are not event
probabilities, warnings, calibrated skill estimates, or guarantees of impact.
Unsupported issues display an explicit unavailable state and never substitute
synthetic fields.

The clean operational export bridge runs the extreme builder automatically for
IFS when its validated private member file is available. If the archive does
not provide three common 2002–2021 starts inside the ±4-day window, the step
exits successfully without changing the issue package and the unavailable state
remains explicit. This makes publication repeatable without weakening the
model-climate matching contract.

### Implementation presentation

The self-contained browser presentation at `presentation.html` explains the
data inputs, weekly aggregation, EFI/SOT definitions, regional paired-member
matrix, schema v3, automation, privacy boundary, and validation gates. Use the
arrow keys or Page Up/Page Down to navigate, `F` for fullscreen, and browser
print for a 16:9 PDF.

Run it locally with:

```bash
npm ci
npm run presentation
```

Then open `http://localhost:5173/presentation.html` if the browser does not open
automatically.

## Data contract

The global contract stores little-endian `uint16` binary arrays in lead-day,
latitude, longitude order: eight ensemble means, eight population standard
deviations, three signed anomaly fields, and separate U/V component means for
850 hPa wind. A one-byte
ocean mask limits SST display support. `metadata.json` locks dimensions,
quantization, units, legends, valid periods, file sizes, and SHA-256 hashes.
The default precipitation layer loads first; other fields load and verify
lazily when selected. The complete optional global payload is about 51 MB
before HTTP compression.

Country boundaries and labels use Natural Earth. `india-admin.json` is a
simplified display derivative of the Survey of India Administrative Boundary
Database state/UT layer and contains no raw shapefile.

The India startup path uses `india-map-geography.json`, a compact,
pre-projected display derivative of those same checked geography files. It
preserves the displayed boundaries while avoiding the full global geography
download and thousands of per-cell SVG nodes. Global metadata and forecast
fields are loaded only when the dated Global Demo route is opened.

The India forecast JSON stores latitude and longitude vectors, a support mask,
six week records, and flattened row-major fields. Every displayed field
contains exactly `latitude.length × longitude.length` finite values.

Source-aware packages live under
`public/data/forecasts/{gfs,era5,ifs}/YYYYMMDD.json`. Each issue links to compact
web JSON, an optional regional-probability package, a product-aware PDF
briefing, and checksums. The website presents only compact derived fields and
the PDF download. Raw initial conditions, NetCDF files, and ensemble-member
fields are never published.

Standard JJAS PDFs contain four rainfall/temperature pages; an issue with the
850 hPa wind capability adds a fifth wind page. Raw-only out-of-season PDFs
contain two pages.
Each page uses a 2 × 2 Weeks 1–4 map layout. The interactive website retains all
six forecast weeks for exploratory research.

The India presentation follows the supplied four-panel PDF structure: one
shared fixed legend, exact reference colour levels, surrounding-country and
India administrative outlines, and selectable Weeks 1–4 or Weeks 3–6 for all
four products. Interpolation is visual only; hover values remain native-grid
values.

The site has no backend. Hash navigation keeps the GitHub Pages deployment
portable, and a failed validation status blocks forecast rendering while
the scientific checks remain internal to the publication workflow.

## Configured domains

`public/data/domains.json` registers named static forecast domains; India stays
the default. To export another 1.5° grid-aligned, non-antimeridian bounding box,
copy `config/custom-domain.example.json` and run:

```bash
python scripts/build_custom_domain.py \
  --config config/my-domain.json \
  --forecast /private/path/to/completed-forecast.nc \
  --source gfs
```

The exporter verifies that the completed forecast output grid exactly matches the
configured center-coordinate bounds, then writes raw Weeks 1–6 rainfall and
temperature JSON, pre-projected Natural Earth geography, a Weeks 1–4 PDF, and
the domain catalog entry. Custom-domain v1 intentionally withholds anomalies,
probabilities, regional summaries, and verification.

## Automation

The production scheduler, clean export/publish bridge, private-state contract,
dry-run procedure, alert setup, and reviewed cron/systemd examples are documented in
[automation/README.md](automation/README.md). No schedule is installed merely
by cloning this repository.

## Deployment

The repository-root `.github/workflows/deploy-pages.yml` builds and deploys the static site to
`https://s2s.scdlds.com/` on push to `main`. `public/CNAME` preserves the custom
hostname in the Pages artifact. During the build it stamps the exact `GITHUB_SHA` into
`public/data/manifest.json`; this avoids the impossible self-referential task
of committing a file containing its own commit hash.

See [PLAN.md](PLAN.md) for the historical one-day prototype design record.
Current automation and release procedures are documented in the Automation
and Deployment sections above.

Global geography is derived from the public-domain Natural Earth 1:110m
administrative boundary dataset.
