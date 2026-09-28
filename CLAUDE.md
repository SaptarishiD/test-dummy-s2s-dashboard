# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope note

The parent directory (`../`) carries its own `CLAUDE.md`/`AGENTS.md` describing a
markdown knowledge wiki at `../wiki/`. That schema governs the wiki only. This
repository is a separate git repo and is not part of it.

`PLAN.md` is a historical design record of the original one-day prototype, not a
roadmap. `README.md`, `automation/README.md`, and `deployment/README.md` describe
the current system.

## Commands

```bash
npm run dev                       # Vite dev server
npm run build                     # tsc --noEmit && vite build — the only frontend check
npm run test:science              # PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
npm run validate:global           # independent global-binary package validation

# one test / one file
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_web_export.py::test_forecast_export_has_six_weeks_and_four_products
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/automation

# public-data gates (no private model data required)
python scripts/validate_operational_publication.py --scope current   # fast pre-publish gate
python scripts/validate_operational_publication.py --scope all       # what CI runs
python scripts/validate_operational_publication.py --scope issue --source ifs --issue 20260909
python scripts/stamp_deploy.py --commit "$SHA"                       # refresh manifest.json
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` is required — the suite is run on hosts with
unrelated pytest plugins installed.

There is no ESLint/Prettier and no requirements.txt. Python needs **3.10+**
(`zip(..., strict=True)` is used) plus `numpy xarray matplotlib shapely pyproj
pyshp jsonschema pytest`; `automation/` itself is stdlib-only. On this machine the
only interpreter carrying the science stack is miniconda 3.9, so
`test_wind850_export.py::test_pdf_builder_creates_one_page_for_each_of_six_products`
fails with `TypeError: zip() takes no keyword arguments` — that is the interpreter,
not the code. `test_web_export.py::test_each_issue_has_one_verified_pdf_download`
also fails in the current tree: the 8-week PDF retention pruned
`era5/20260715`'s download while its catalog entry remained.

Builders that need the private NetCDF inputs (cluster paths, defaults in
`scripts/validate_sources.py`, all overridable by CLI flag) cannot run locally:
`validate_sources.py`, `build_prototype_data.py`, `export_global_forecast.py`,
`build_custom_domain.py`, `build_initialization_comparison.py`, `validate_web_data.py`.

## Architecture

Three layers, strictly one-directional:

1. **Private scientific inputs** — FuXi forecast/reforecast NetCDF, IMD/IMERG
   climatologies, shapefiles. Never in this repo, referenced only by path.
2. **Python export + validation** (`science/`, `scripts/`) — reads private inputs,
   writes compact public artifacts into `public/data/`.
3. **Static frontend** (`src/`) — reads `public/data/` over `fetch`, nothing else.
   No backend, no runtime dependencies, hash routing so GitHub Pages stays portable.

### `science/` is the single source of scientific truth

- `formulas.py` — every locked formula (unit conversions, weekly reductions,
  anomalies, spread `ddof=0` vs climatology `ddof=1`, terciles, verification
  weights). Import it; never re-derive a formula in a script or in TypeScript.
- `contracts.py` — frozen dataclasses pinning the India grid (27×27, 1.5°, 39°N→0°N,
  60°E→99°E), forecast shape (100 members, 42 leads), and climatology identities
  with their exact baselines and sample counts.
- `validators.py` — ordered gates: file integrity/SHA-256 → structure → physical
  plausibility → publication safety.
- `catalog.py` — builds `public/data/index.json`: per-source issue lists, `current`
  and `latest_reference` pointers, per-issue capabilities, cadence, retention.
  `PRIMARY_SOURCE_ID = "ifs"`; cadence is Wednesday/Sunday.

### Public data contract (`public/data/`)

- `index.json` (`schema_version: 3`) is the map the frontend loads first, via
  `domains.json` → active domain → its catalog.
- `forecasts/{ifs,gfs,era5}/YYYYMMDD.json` — compact weekly fields with latitude /
  longitude vectors, support mask, and flattened row-major values. Every displayed
  field must hold exactly `latitude.length × longitude.length` finite numbers.
- `regional/<source>/YYYYMMDD.json` tercile outlooks, `comparisons/` matched
  initialization pairs, `global/*.bin` + `global/metadata.json` (little-endian
  `uint16`, lead-day × lat × lon, with locked sizes and SHA-256).
- `manifest.json` is the checksum inventory; CI stamps `GITHUB_SHA` into it at build
  time, which is why it is not consistent with itself in a local checkout.
- Assets are cache-busted by content hash: `checksumVersionedPath()` /
  `issueChecksum()` in `src/lib/catalog.ts`. Catalog and geography JSON use
  `cache: "no-store"` instead.

Three initialization sources are kept deliberately independent and are never
interchangeable: **IFS** (main experimental guidance), **GFS** (secondary
near-real-time proxy, no matched hindcast calibration), **ERA5** (delayed
reference). Source selection, labels, and capability gating all flow from the
catalog, not from hardcoded frontend assumptions.

### Frontend (`src/`)

- `main.ts` owns routing: hash routes `india | archive | briefing | team`, one
  dynamic `import()` per route, and a `routeCleanup` teardown callback returned by
  the page renderer. A load failure renders a blocked state — never a partial map.
- `pages/global.ts` and `pages/outlook.ts` export working renderers that `main.ts`
  no longer imports (the Global Demo and outlook routes were retired from the nav).
  They are still type-checked and asserted on by tests; don't delete them as dead code.
- `components/` draw raw SVG by hand (no d3, no charting library): `ForecastMap`,
  `TercileProbabilityMap`, `GlobalForecastMap`, `Legend`.
- `types.ts` mirrors the Python-produced JSON by hand — change it in lockstep with
  the exporters in `scripts/`.
- `index.html` sets a strict CSP (`default-src 'self'`, no inline or remote scripts).
  Nothing may be loaded from a CDN.

### Tests are contract tests, not unit tests

`tests/test_ui_structure.py` and `tests/test_public_copy.py` assert on the **text**
of the TypeScript and CSS sources — exact `setAttribute` calls, SVG paint order,
constant names, user-facing copy, contact addresses. Renaming a local, reordering
map layers, or rewording a label in `src/` will fail Python tests. Read the relevant
assertions before refactoring UI code, and update them deliberately.

The rest of `tests/` pins the published artifacts: catalog pointers, finite fields,
checksums, retention behaviour, year-round (non-JJAS) product withholding, wind
products, and the publication bridge.

### Publication and automation

Not run from a developer checkout. `automation/fuxi_scheduler.py` polls per source
and advances an atomic private state record
`pending → submitted → validated → exported → pushed → deployed` (or `failed`;
failures are never auto-resubmitted). Publication goes through
`scripts/export_and_publish_operational_issue.py` →
`scripts/publish_operational_site.py`, both using disposable git worktrees off a
dedicated publishing clone, fast-forward pushes only, never `--force`.
`.github/workflows/deploy-pages.yml` then stamps the commit, validates the current
issues and the whole archive, validates the global package, type-checks, builds,
deploys, and runs `scripts/postdeploy_smoke.py` against the live URL.

## Hard rules

- **Never commit private content.** `validate_web_data.py`'s
  `FORBIDDEN_PUBLIC_PATTERNS` rejects `/storage/`, `/home/`, private-key blocks, and
  `password|secret|access_token` assignments in any public file. Raw NetCDF,
  ensemble members, reforecasts, model weights, observations, and credentials stay
  out of `public/`.
- **No non-finite JSON.** `NaN`/`Infinity` in public JSON is a publication failure.
- **Don't hand-edit `public/data/`.** Regenerate through the scripts so fields,
  catalog pointers, checksums, and the manifest stay mutually consistent.
- **Anomalies and probabilities require a matched climatology.** Outside the
  validated JJAS window, publish raw weekly rainfall and mean temperature only and
  withhold anomalies, regional probabilities, and wind augmentation.
- The public identity is the neutral "S2S Research"; model identity and provenance
  live in this repository's code and docs, not in the interface copy.
