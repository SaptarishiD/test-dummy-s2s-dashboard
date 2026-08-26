"""Focused source-level contracts for the lightweight TypeScript UI."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_forecast_map_places_coordinate_labels_outside_the_plot() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    assert "const AXIS_LEFT" in forecast_map
    assert "const AXIS_BOTTOM" in forecast_map
    assert 'class", "map-coordinate map-coordinate--longitude"' in forecast_map
    assert 'class", "map-coordinate map-coordinate--latitude"' in forecast_map
    assert "AXIS_LEFT + x" in forecast_map
    assert "this.mapHeight + 20" in forecast_map


def test_india_forecast_paint_and_wind_are_clipped_to_the_abdb_outline() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    forecast_page = read("src/pages/forecast.ts")

    assert (
        'indiaDataClipPath.setAttribute("d", this.geography.india_outline_path)'
        in forecast_map
    )
    assert (
        'image.setAttribute("clip-path", `url(#${indiaDataClipPathId})`)'
        in forecast_map
    )
    assert forecast_map.count(
        'group.setAttribute("clip-path", `url(#${indiaDataClipPathId})`)'
    ) == 2
    assert "Survey of India ABDB display derivative" in forecast_page
    assert "Source: Survey of India, Government of India." in forecast_page
    assert "Non-India political boundaries are intentionally omitted" in forecast_page


def test_wind_streamlines_are_default_with_an_arrow_alternative() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    forecast_page = read("src/pages/forecast.ts")
    assert 'export type WindRenderingMode = "streamlines" | "arrows"' in forecast_map
    assert 'windRenderingMode: WindRenderingMode = "streamlines"' in forecast_map
    assert "traceStreamlineDirection(" in forecast_map
    assert "sampleWindVector(" in forecast_map
    assert 'class", "map-wind-streamline map-wind-vector"' in forecast_map
    assert 'wind850_mean: 10' in forecast_map
    assert 'wind850_anomaly: 5' in forecast_map
    assert "const vectors = week.vectors?.[productKey]" in forecast_map
    assert 'data-wind-mode="streamlines" class="is-active"' in forecast_page
    assert 'data-wind-mode="arrows"' in forecast_page
    assert 'windModeControl.hidden = !isWindProduct(selectedProduct)' in forecast_page
    assert 'product === "wind850_mean" || product === "wind850_anomaly"' in forecast_page
    assert "map.render(selectedProduct, week, product, windRenderingMode)" in forecast_page


def test_forecast_uses_gfs_current_without_conflating_source_latest_issues() -> None:
    catalog = read("src/lib/catalog.ts")
    forecast = read("src/pages/forecast.ts")
    assert 'sourceById(index, index.default_source)' in catalog
    assert "if (index.current)" in catalog
    assert "source.id === index.current.source_id" in catalog
    assert 'Current · Experimental GFS proxy' in forecast
    assert 'Latest source issue · Experimental IFS' in forecast
    assert 'Latest experimental IFS issue—not the current forecast' in forecast


def test_archive_distinguishes_ifs_from_the_gfs_proxy() -> None:
    archive = read("src/pages/archive.ts")
    assert 'source.id === "ifs"' in archive
    assert 'Experimental operational initialization' in archive
    assert 'Operational-input proxy' in archive


def test_operational_refresh_is_imported_after_the_legacy_styles() -> None:
    main = read("src/main.ts")
    refresh = read("src/styles/operational.css")
    assert main.index('import "./styles/main.css"') < main.index(
        'import "./styles/operational.css"'
    )
    assert "--ops-canvas" in refresh
    assert ".india-run-console" in refresh
    assert ".archive-controls" in refresh
    assert ".briefing-report-summary" in refresh
    assert ".team-roster" in refresh
    assert ".team-grid" in refresh


def test_scientific_team_has_a_dedicated_route() -> None:
    main = read("src/main.ts")
    briefing = read("src/pages/briefing.ts")
    team = read("src/pages/team.ts")
    assert 'type Route = "india" | "archive" | "briefing" | "team"' in main
    assert 'href="./#team" data-route="team"' in main
    assert 'document.body.classList.toggle("team-route", route === "team")' in main
    assert 'await import("./pages/team")' in main
    assert "renderTeamPage(content)" in main
    assert 'class="team-page"' in team
    assert 'class="team-grid"' in team
    assert 'aria-label="Contributors ordered by project responsibility"' in team
    assert 'class="briefing-team"' not in briefing


def test_forecast_explains_initial_condition_sources_accessibly() -> None:
    forecast = read("src/pages/forecast.ts")
    assert 'class="india-source-guide"' in forecast
    assert 'id="india-source-guide"' in forecast
    assert 'aria-describedby="india-source-guide india-source-date-notice"' in forecast
    assert 'aria-label="Explain IFS, GFS, and ERA5 sources"' in forecast
    assert "Integrated Forecasting System" in forecast
    assert "Global Forecast System" in forecast
    assert "Delayed ECMWF reanalysis reference" in forecast
    assert "same experimental forecasting system is initialized" in forecast


def test_forecast_warns_that_source_latest_dates_can_differ() -> None:
    forecast = read("src/pages/forecast.ts")
    refresh = read("src/styles/operational.css")
    assert "const preferredIssues = new Map(" in forecast
    assert "defaultIssueForSource(index, candidate)" in forecast
    assert 'id="india-source-date-notice"' in forecast
    assert "Latest validated:" in forecast
    assert "Dates can differ between sources" in forecast
    assert "opens its latest validated initialization" in forecast
    assert ".india-source-date-notice" in refresh


def test_forecast_date_formatter_accepts_full_iso_initializations() -> None:
    forecast = read("src/pages/forecast.ts")
    assert "const calendarDate = isoDate.slice(0, 10);" in forecast
    assert "new Date(`${calendarDate}T12:00:00Z`)" in forecast
    assert "friendlyDate(preferred.initialization, true)" in forecast
    assert "new Date(`${isoDate}T12:00:00Z`)" not in forecast


def test_forecast_idle_product_rotation_is_controlled_and_cleaned_up() -> None:
    main = read("src/main.ts")
    forecast = read("src/pages/forecast.ts")
    expected_order = (
        '"rainfall_anomaly"',
        '"rainfall_total"',
        '"wind850_anomaly"',
        '"temperature_anomaly"',
    )
    order_start = forecast.index("const AUTO_PRODUCT_ORDER")
    order_end = forecast.index("];", order_start)
    order_block = forecast[order_start:order_end]
    assert '"wind850_mean"' not in order_block
    assert [order_block.index(product) for product in expected_order] == sorted(
        order_block.index(product) for product in expected_order
    )
    assert "AUTO_PRODUCT_DELAY_MS = 12_000" in forecast
    assert "AUTO_PRODUCT_IDLE_DELAY_MS = 30_000" in forecast
    assert "AUTO_PRODUCT_ORDER.filter" in forecast
    assert 'id="india-auto-cycle"' in forecast
    assert 'aria-pressed="true"' in forecast
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in forecast
    assert 'document.addEventListener("visibilitychange"' in forecast
    assert "return () => {" in forecast
    assert "clearAutoCycleTimer();" in forecast
    assert "routeCleanup?.();" in main
    assert "routeCleanup = renderForecastPage(content, data);" in main


def test_raw_wind_is_retained_in_data_but_hidden_from_the_website() -> None:
    catalog = read("src/lib/catalog.ts")
    archive = read("src/pages/archive.ts")
    types = read("src/types.ts")

    product_keys_start = catalog.index("const PRODUCT_KEYS")
    product_keys_end = catalog.index("];", product_keys_start)
    product_keys = catalog[product_keys_start:product_keys_end]
    assert '"wind850_mean"' in product_keys
    assert '"wind850_anomaly"' in product_keys
    assert 'Exclude<AvailableProductKey, "wind850_mean">' in catalog
    assert 'return product !== "wind850_mean"' in catalog
    assert "return WEBSITE_PRODUCT_KEYS.filter(" in catalog
    assert "productIsWebsiteVisible(product)" in archive
    assert 'wind850_mean: "850 hPa wind"' not in archive
    assert 'wind850_anomaly: "850 hPa wind anomaly"' in archive
    assert 'export type WindProductKey = "wind850_mean" | "wind850_anomaly"' in types


def test_forecast_has_a_prominent_full_briefing_action() -> None:
    forecast = read("src/pages/forecast.ts")
    refresh = read("src/styles/operational.css")
    assert 'class="india-briefing-cta" href="./#briefing"' in forecast
    assert "Summary and full report" in forecast
    assert 'class="india-pdf-download-secondary"' in forecast
    assert 'class="india-pdf-download-tertiary"' in forecast
    assert ".india-run-actions .india-briefing-cta" in refresh
    assert ".site-nav .briefing-nav-link.is-active" in refresh
