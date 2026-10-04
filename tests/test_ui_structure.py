"""Focused source-level contracts for the lightweight TypeScript UI."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def rule_body(style: str, selector: str) -> str:
    """Return the declarations of the first rule matching ``selector``."""

    start = style.index(selector) + len(selector)
    return style[start : style.index("}", start)]


def test_forecast_map_places_coordinate_labels_outside_the_plot() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    assert "const AXIS_LEFT" in forecast_map
    assert "const AXIS_BOTTOM" in forecast_map
    assert 'class", "map-coordinate map-coordinate--longitude"' in forecast_map
    assert 'class", "map-coordinate map-coordinate--latitude"' in forecast_map
    assert "AXIS_LEFT + x" in forecast_map
    assert "this.mapHeight + 20" in forecast_map


def test_forecast_map_inspection_is_keyboard_touch_and_edge_safe() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    assert 'this.tooltip.setAttribute("role", "tooltip")' in forecast_map
    assert '"aria-keyshortcuts"' in forecast_map
    assert 'marker.setAttribute("class", "map-sample-marker")' in forecast_map
    assert 'interactionSurface.addEventListener("pointerdown"' in forecast_map
    assert 'interactionSurface.addEventListener("pointerup"' in forecast_map
    assert 'interactionSurface.addEventListener("pointercancel"' in forecast_map
    assert "let tapCandidate:" in forecast_map
    assert "Math.hypot(" in forecast_map
    assert 'svg.addEventListener("keydown"' in forecast_map
    assert "ArrowUp: [-1, 0]" in forecast_map
    assert "ArrowRight: [0, 1]" in forecast_map
    assert "const maximumLeft = Math.max(" in forecast_map
    assert "const maximumTop = Math.max(" in forecast_map


def test_india_maps_keep_the_original_full_regional_paint_order() -> None:
    forecast_map = read("src/components/ForecastMap.ts")
    forecast_page = read("src/pages/forecast.ts")
    outlook_map = read("src/components/TercileProbabilityMap.ts")

    field = forecast_map.index("this.addInterpolatedField(plot")
    world = forecast_map.index("this.addWorldBoundaries(plot)")
    graticules = forecast_map.index("this.addGraticules(plot, svg)")
    assert field < world < graticules
    assert "indiaDataClipPathId" not in forecast_map

    outlook_field = outlook_map.index(
        "this.addProbabilityField(svg, variable, week);"
    )
    outlook_world = outlook_map.index("this.addWorldBoundaries(svg);")
    outlook_outline = outlook_map.index("this.addOutline(svg);")
    assert outlook_field < outlook_world < outlook_outline
    assert "Survey of India ABDB display derivative" not in forecast_page


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
    assert 'selectedView !== "mean" || !isWindProduct(selectedProduct)' in forecast_page
    assert 'product === "wind850_mean" || product === "wind850_anomaly"' in forecast_page
    assert "map.render(selectedProduct, week, product, windRenderingMode)" in forecast_page


def test_forecast_uses_ifs_as_main_without_conflating_source_latest_issues() -> None:
    catalog = read("src/lib/catalog.ts")
    forecast = read("src/pages/forecast.ts")
    assert 'sourceById(index, index.default_source)' in catalog
    assert "if (index.current)" in catalog
    assert "source.id === index.current.source_id" in catalog
    assert "IFS is the main forecast" in forecast
    assert "GFS is a secondary proxy" in forecast
    assert 'Latest GFS proxy—not the main forecast' in forecast
    assert 'candidate.id === index.default_source ? "Main forecast"' in forecast
    assert '"Secondary proxy"' in forecast


def test_initial_condition_sources_present_ifs_first_and_gfs_last() -> None:
    catalog = read("src/lib/catalog.ts")
    forecast = read("src/pages/forecast.ts")
    archive = read("src/pages/archive.ts")
    outlook = read("src/pages/outlook.ts")
    assert '"ifs",\n  "era5",\n  "gfs",' in catalog
    assert "INITIAL_CONDITION_SOURCE_DISPLAY_ORDER.filter(" in forecast
    assert "const displaySources = sourcesForDisplay(index);" in forecast
    assert "sourcesForDisplay(activeIndex).map((source)" in archive
    assert "sourcesForDisplay(index).map((candidate)" in outlook


def test_forecast_exposes_active_product_for_presentation_theming() -> None:
    forecast = read("src/pages/forecast.ts")
    stylesheet = read("src/styles/operational.css")
    assert 'class="india-sheet" data-product="${defaultProduct}"' in forecast
    assert '.dataset.product =\n      selectedProduct' in forecast
    assert '.india-sheet[data-product="rainfall_total"]' in stylesheet
    assert '.india-sheet[data-product="rainfall_anomaly"]' in stylesheet
    assert '.india-sheet[data-product="temperature_mean"]' in stylesheet
    assert '.india-sheet[data-product="temperature_anomaly"]' in stylesheet
    assert '.india-sheet[data-product="wind850_mean"]' in stylesheet
    assert '.india-sheet[data-product="wind850_anomaly"]' in stylesheet


def test_forecast_hero_presents_the_title_and_timing_cleanly() -> None:
    forecast = read("src/pages/forecast.ts")
    assert '<h1>India six-week forecast maps</h1>' in forecast
    assert 'class="india-forecast-window" aria-label="Forecast timing"' in forecast
    assert "<dt>Forecast run</dt>" in forecast
    assert "· 00 UTC</dd>" in forecast
    assert "<dt>Maps cover</dt>" in forecast
    assert "<dt>Available</dt><dd>Weeks 1–6</dd>" in forecast
    assert '<h1 class="ops-visually-hidden">India six-week forecast maps</h1>' not in forecast


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
    assert 'class="team-directory"' in team
    assert 'class="team-directory__header"' in team
    assert 'class="team-grid"' in team
    assert 'aria-label="Research contributors"' in team
    assert 'aria-describedby="team-order-note"' in team
    assert 'class="team-grid" role="list"' in team
    assert 'role="listitem"' in team
    assert 'class="team-contact"' in team
    assert 'aria-labelledby="team-contact-title"' in team
    assert ".team-contact__email" in read("src/styles/operational.css")
    assert 'class="briefing-team"' not in briefing


def test_team_roster_renders_labelled_groups_of_centred_cards() -> None:
    team = read("src/pages/team.ts")
    style = read("src/styles/operational.css")

    # One labelled directory block per group, each one its own list.
    assert "function renderGroup(group: TeamGroup): string" in team
    assert "${TEAM_GROUPS.map(renderGroup).join(\"\")}" in team
    assert '<h2 class="team-directory__header" id="${headingId}">' in team
    assert 'class="team-grid" role="list" aria-labelledby="${headingId}"' in team
    # The group label is the h2, so each person drops to an h3.
    assert '<h3 id="${memberId}">${member.name}</h3>' in team
    assert ".team-person-card h3 {" in style
    assert ".team-person-card h2 {" not in style

    grid = rule_body(style, ".team-grid {")
    assert "display: flex" in grid
    assert "flex-wrap: wrap" in grid
    assert "justify-content: center" in grid

    card = rule_body(style, ".team-person-card {")
    assert "flex-direction: column" in card
    assert "text-align: center" in card

    portrait = rule_body(style, ".team-person-card__portrait {")
    assert "border-radius: 50%" in portrait

    # The retired table layout must not linger in any breakpoint.
    assert '"portrait identity"' not in style
    assert "grid-area: portrait" not in style
    assert ".team-directory__header span:first-child" not in style


def test_forecast_explains_initial_condition_sources_accessibly() -> None:
    forecast = read("src/pages/forecast.ts")
    stylesheet = read("src/styles/operational.css")
    assert 'class="india-source-guide"' in forecast
    assert 'id="india-source-guide"' in forecast
    assert 'aria-describedby="india-source-guide india-source-date-notice"' in forecast
    assert 'aria-label="Explain IFS, GFS, and ERA5 sources"' in forecast
    assert "Integrated Forecasting System" in forecast
    assert "Global Forecast System" in forecast
    assert "Delayed ECMWF reanalysis reference" in forecast
    assert "same experimental forecasting system is initialized" in forecast
    assert ".india-source-guide[open]" in stylesheet
    assert ".india-source-tabs a:focus-visible" in stylesheet
    assert "outline-offset: -3px" in stylesheet
    assert "--ops-ink-faint: #5d6c7e" in stylesheet


def test_forecast_explains_that_source_latest_dates_can_differ() -> None:
    forecast = read("src/pages/forecast.ts")
    refresh = read("src/styles/operational.css")
    assert "const preferredIssues = new Map(" in forecast
    assert "defaultIssueForSource(index, candidate)" in forecast
    assert 'id="india-source-date-notice"' in forecast
    assert "Latest validated runs" in forecast
    assert "Sources update on different dates" in forecast
    assert "opens its latest run" in forecast
    assert ".india-source-date-notice" in refresh


def test_forecast_removes_redundant_instructions_and_metadata() -> None:
    forecast = read("src/pages/forecast.ts")
    assert "Explore the maps" not in forecast
    assert "Choose a variable" not in forecast
    assert "IFS-main" not in forecast
    assert "Main · Experimental IFS initialization" not in forecast
    assert 'class="india-status-grid"' not in forecast
    assert "Sources and downloads" in forecast
    assert "Open forecast PDF" in forecast
    assert "Download PDF" in forecast
    assert "Browse archive" in forecast


def test_forecast_date_formatter_accepts_full_iso_initializations() -> None:
    forecast = read("src/pages/forecast.ts")
    assert "const calendarDate = isoDate.slice(0, 10);" in forecast
    assert "new Date(`${calendarDate}T12:00:00Z`)" in forecast
    assert "friendlyDate(preferred.initialization, true)" in forecast
    assert "new Date(`${isoDate}T12:00:00Z`)" not in forecast


def test_forecast_variable_and_week_selection_are_manual_and_accessible() -> None:
    main = read("src/main.ts")
    forecast = read("src/pages/forecast.ts")
    assert "AUTO_PRODUCT_ORDER" not in forecast
    assert 'id="india-auto-cycle"' not in forecast
    assert 'id="india-range-select"' in forecast
    assert '<option value="0">Weeks 1–4</option>' in forecast
    assert '<option value="2">Weeks 3–6</option>' in forecast
    assert "productIcon(productKey)" in forecast
    assert 'india-variable-icon--rainfall"' in forecast
    assert 'india-variable-icon--rainfall-anomaly"' in forecast
    assert 'india-variable-icon--temperature"' in forecast
    assert 'india-variable-icon--temperature-anomaly"' in forecast
    assert 'india-variable-icon--wind"' in forecast
    assert "-webkit-backdrop-filter: blur(24px) saturate(150%)" in read(
        "src/styles/operational.css"
    )
    assert 'button.setAttribute("aria-pressed", String(active))' in forecast
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in forecast
    assert 'class="india-visualization" id="india-visualization"' in forecast
    assert 'class="india-map-workspace"' in forecast
    assert 'productIndicator.className = "india-product-indicator"' in forecast
    assert 'typeof document.startViewTransition === "function"' in forecast
    assert 'window.removeEventListener("resize", positionProductIndicator)' in forecast
    assert "return () => {" in forecast
    assert "panelAnimationTimer" in forecast
    assert "routeCleanup?.();" in main
    assert "routeCleanup = renderForecastPage(content, data);" in main


def test_forecast_explains_the_selected_product_below_the_maps() -> None:
    forecast = read("src/pages/forecast.ts")
    assert "PLAIN_LANGUAGE_PRODUCT_DESCRIPTIONS" in forecast
    assert 'class="india-map-key"' in forecast
    assert 'id="india-product-explanation"' in forecast
    assert "wetter or drier" in forecast
    assert "warmer or cooler" in forecast
    assert forecast.index('id="india-panel-grid"') < forecast.index(
        'id="india-product-explanation"'
    )
    assert "Showing ${product.label}." in forecast
    assert "Showing Weeks ${rangeStart + 1}–${rangeStart + 4}." in forecast


def test_forecast_map_headers_prioritize_week_and_semantic_dates() -> None:
    forecast = read("src/pages/forecast.ts")
    assert 'class="india-map-panel__period"' in forecast
    assert '<time datetime="${week.valid_start}">' in forecast
    assert '<time datetime="${week.valid_end}">' in forecast
    assert "<i>|</i>" not in forecast


def test_forecast_polish_uses_one_workspace_rail_and_desktop_sticky_controls() -> None:
    stylesheet = read("src/styles/operational.css")
    assert "--india-workspace-width: 1180px" in stylesheet
    assert "view-transition-name: india-forecast-visualization" in stylesheet
    assert "@media (min-width: 1181px)" in stylesheet
    assert "--product-indicator-x" in stylesheet
    assert ".india-map-panel:focus-within" in stylesheet
    assert "scroll-margin-top: 92px" in stylesheet
    assert ".india-product-tabs button::after," in stylesheet
    assert ".skip-link {" in stylesheet


def test_skip_link_does_not_enter_the_hash_router() -> None:
    main = read("src/main.ts")
    assert 'querySelector<HTMLAnchorElement>(".skip-link")' in main
    assert "event.preventDefault();" in main
    assert "content.focus({ preventScroll: true });" in main
    assert "focusContentAfterRoute" in main
    assert "hasRenderedRoute" in main
    assert "rememberRouteFocus();" in main
    assert "ROUTE_FOCUS_STORAGE_KEY" in main


def test_mean_and_anomalous_wind_are_available_on_the_website() -> None:
    catalog = read("src/lib/catalog.ts")
    archive = read("src/pages/archive.ts")
    types = read("src/types.ts")

    product_keys_start = catalog.index("const MEAN_PRODUCT_KEYS")
    product_keys_end = catalog.index("];", product_keys_start)
    product_keys = catalog[product_keys_start:product_keys_end]
    assert '"wind850_mean"' in product_keys
    assert '"wind850_anomaly"' in product_keys
    assert 'export type WebsiteProductKey = AvailableProductKey' in catalog
    assert "return WEBSITE_PRODUCT_KEYS.filter(" in catalog
    assert 'wind850_mean: "850 hPa wind"' in archive
    assert 'wind850_anomaly: "850 hPa wind anomaly"' in archive
    assert 'export type WindProductKey = "wind850_mean" | "wind850_anomaly"' in types


def test_forecast_has_a_prominent_full_briefing_action() -> None:
    forecast = read("src/pages/forecast.ts")
    refresh = read("src/styles/operational.css")
    assert 'class="india-hero-briefing" href="./#briefing"' in forecast
    assert "Plain-language summary and full report" in forecast
    assert 'class="india-pdf-download-secondary"' in forecast
    assert 'class="india-pdf-download-tertiary"' in forecast
    assert ".india-hero-briefing" in refresh
    assert '.site-nav a[aria-current="page"]' in refresh


def test_shared_header_uses_the_page_rail_and_purpose_labeled_navigation() -> None:
    main = read("src/main.ts")
    stylesheet = read("src/styles/operational.css")
    assert 'class="site-header__inner"' in main
    assert 'class="institution-brand__marks"' in main
    assert 'class="institution-brand__service"' in main
    assert main.index('data-route="briefing"') < main.index('data-route="archive"')
    assert "Latest maps" in main
    assert "Weekly analysis" in main
    assert "Past issues" in main
    assert "People &amp; methods" in main
    assert "briefing-nav-link__icon" not in main
    assert "width: min(calc(100% - 48px), 1180px)" in stylesheet
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in stylesheet
    assert ".site-nav a[aria-current=\"page\"]::after" in stylesheet
    assert ".site-nav a:focus-visible" in stylesheet
    assert ".site-nav a::after," in stylesheet
    assert 'headerUtility.hidden = route === "team"' in main
    assert "Latest run ·" in main
    assert "Latest briefing · ${FEATURED_REPORT.date}" in main
    assert "Catalogue through ·" in main


def test_forecast_integrates_uncertainty_and_extreme_views_without_replacing_mean() -> None:
    forecast = read("src/pages/forecast.ts")
    assert 'data-forecast-view="mean" class="is-active"' in forecast
    assert 'data-forecast-view="probability"' in forecast
    assert 'data-forecast-view="spread"' in forecast
    assert 'data-forecast-view="extremes"' in forecast
    assert 'let selectedView: ForecastView = "mean"' in forecast
    assert 'const meanCandidates: ProductKey[]' in forecast
    assert 'if (matchingMeanProduct) selectedProduct = matchingMeanProduct' in forecast
    assert 'value="most_likely">Most likely tercile' in forecast
    assert 'value="below_normal"' in forecast
    assert 'value="near_normal"' in forecast
    assert 'value="above_normal"' in forecast
    assert "selectedLocation" in forecast
    assert "rangeStart" in forecast
    assert "selectedProbabilityVariable" in forecast
    assert "map.render(selectedProduct, week, product, windRenderingMode)" in forecast


def test_extreme_interface_prioritizes_efi_and_progressively_discloses_detail() -> None:
    forecast = read("src/pages/forecast.ts")
    panel = read("src/components/ExtremeForecastPanel.ts")
    outlook = read("src/pages/outlook.ts")
    assert 'class="india-extreme-primary is-active"' in forecast
    assert "Advanced maps: SOT" in forecast
    assert 'class="extreme-panel__advanced"' in panel
    assert "Advanced distribution details" in panel
    assert "Forecast versus model climate" in panel
    assert "data-extreme-variable" not in panel
    assert "Joint raw member fractions" not in outlook
    assert "outlook-joint" not in outlook


def test_implementation_presentation_is_a_keyboard_operable_vite_entry() -> None:
    presentation = read("presentation.html")
    controller = read("src/presentation.ts")
    stylesheet = read("src/styles/presentation.css")
    vite = read("vite.config.ts")
    package = read("package.json")
    assert presentation.count('class="slide') >= 12
    assert 'id="slide-12"' in presentation
    assert "Extreme Forecast Index" in presentation
    assert "Compact distribution summary" in presentation
    assert "Paired regional outcomes" not in presentation
    assert "Future compatible IFS issues are enriched automatically" in presentation
    assert 'data-action="fullscreen"' in presentation
    assert 'event.key === "Home"' in controller
    assert 'event.key === "End"' in controller
    assert 'event.key.toLowerCase() === "f"' in controller
    assert "@media print" in stylesheet
    assert 'input: ["index.html", "presentation.html"]' in vite
    assert (
        '"presentation": "npm run build && vite preview --open /presentation.html"'
        in package
    )


def test_probabilistic_data_is_lazy_versioned_and_stale_safe() -> None:
    forecast = read("src/pages/forecast.ts")
    assert "async function loadRegionalOutlook()" in forecast
    assert 'issueChecksum(catalogIssue!, "regional_outlook")' in forecast
    assert "checksumVersionedPath(" in forecast
    assert "const requestController = new AbortController()" in forecast
    assert "generation !== requestGeneration" in forecast
    assert "requestController.abort()" in forecast
    assert "No distribution has been reconstructed from the ensemble mean" in forecast


def test_probability_map_distinguishes_ties_missing_data_and_spread() -> None:
    probability_map = read("src/components/ProbabilisticForecastMap.ts")
    assert '"most_likely"' in probability_map
    assert 'options.product === "spread"' in probability_map
    assert '"No unique leading category"' in probability_map
    assert 'kind: "tie" | "missing"' in probability_map
    assert "p90_minus_p10" in probability_map
    assert "const SPREAD_STOPS" in probability_map
    assert "const SPREAD_COLORS" in probability_map
    assert "spreadColor(" in probability_map
    assert "valid_member_count" in probability_map
    assert "Raw ensemble probability" in probability_map
    assert "ArrowUp ArrowDown ArrowLeft ArrowRight Enter Space" in probability_map
    assert 'extent: "india" | "regional"' in probability_map
    assert 'options.extent === "regional"' in probability_map
    assert 'options.extent === "india"' in probability_map


def test_spread_view_can_reveal_the_available_regional_grid() -> None:
    forecast = read("src/pages/forecast.ts")
    stylesheet = read("src/styles/probabilistic.css")
    assert 'id="india-probability-extent" hidden' in forecast
    assert 'value="regional">Regional grid (60–99°E)' in forecast
    assert 'selectedProbabilityExtent: "india" | "regional" = "regional"' in forecast
    assert 'probabilityExtentControl.hidden = selectedView === "mean" || selectedView === "extremes"' in forecast
    assert "extent: selectedProbabilityExtent" in forecast
    assert "but not all of Thailand or Indonesia" in forecast
    assert ".india-product-tabs[hidden]" in stylesheet
    assert ".india-probability-extent[hidden]" in stylesheet


def test_location_panel_labels_grid_support_and_ensemble_intervals_honestly() -> None:
    panel = read("src/components/LocationForecastPanel.ts")
    stylesheet = read("src/styles/probabilistic.css")
    assert "not a district or regional average" in panel
    assert "80% ensemble interval" in panel
    assert "not a confidence interval or a skill estimate" in panel
    assert "P25–P75" in panel
    assert "P10–P90" in panel
    assert "they are not smoothed or forced to widen" in panel
    assert "Raw ensemble probability" in panel
    assert "weeklyTercileEvolution(" in panel
    assert "selectedWeekRangeStrip(" in panel
    assert "forecastFingerprint(" in panel
    assert "Six-week forecast fingerprint" in panel
    assert "P10–P90 range" in panel
    assert "Tercile evolution across forecast weeks" in panel
    assert "Threshold-exceedance curve unavailable" in panel
    assert "Member histogram unavailable" in panel
    assert "Weekly transition probabilities unavailable" in panel
    assert "Probabilistic verification pending observations" in panel
    assert ".probability-weekly-terciles" in stylesheet
    assert ".probability-range-strip" in stylesheet
    assert ".probability-fingerprint" in stylesheet
    assert ".probability-location-host" in stylesheet
    assert "position: fixed" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet


def test_member_derived_percentiles_and_category_margin_are_exposed() -> None:
    forecast = read("src/pages/forecast.ts")
    probability_map = read("src/components/ProbabilisticForecastMap.ts")
    types = read("src/types.ts")
    assert 'value="category_margin">Leading-category margin' in forecast
    assert 'value="p10">P10 lower outcome' in forecast
    assert 'value="p50">Median outcome' in forecast
    assert 'value="p90">P90 upper outcome' in forecast
    assert "Threshold exceedance probability" in forecast
    assert 'DistributionMapProduct = "spread" | "p10" | "p50" | "p90"' in types
    assert "const PERCENTILE_STOPS" in probability_map
    assert "const CATEGORY_MARGIN_STOPS" in probability_map
    assert "categoryMargin(" in probability_map
    assert "Not confidence or forecast skill" in probability_map
