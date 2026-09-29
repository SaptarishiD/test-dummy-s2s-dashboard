import {
  ForecastMap,
  type WindRenderingMode,
} from "../components/ForecastMap";
import { createLegend } from "../components/Legend";
import { ProbabilisticForecastMap } from "../components/ProbabilisticForecastMap";
import { renderLocationForecastPanel } from "../components/LocationForecastPanel";
import { renderExtremeForecastPanel } from "../components/ExtremeForecastPanel";
import {
  checksumVersionedPath,
  currentForecast,
  defaultIssueForSource,
  extremeProductKeysForForecast,
  INITIAL_CONDITION_SOURCE_DISPLAY_ORDER,
  issueChecksum,
  issueHasRegionalOutlook,
  issueIsCurrent,
  productKeysForForecast,
  sourcesForDisplay,
} from "../lib/catalog";
import type {
  AppData,
  DistributionMapProduct,
  ForecastWeek,
  ForecastData,
  ForecastGridSelection,
  InitializationComparisonData,
  InitialConditionSourceId,
  ProbabilityMapProduct,
  ProbabilisticVariable,
  ProductDefinition,
  ProductKey,
  RegionalOutlookData,
} from "../types";

const COMPARISON_PRODUCTS = {
  rainfall: {
    sourceKey: "rainfall_total" as ProductKey,
    differenceProduct: {
      label: "Rainfall difference",
      short_label: "Rainfall difference",
      description: "Pairwise ensemble-mean rainfall difference",
      units: "mm day⁻¹",
      baseline: null,
      legend: {
        boundaries: [-20, -10, -5, -2, -1, 1, 2, 5, 10, 20],
        colors: [
          "#8b2b15", "#cf6135", "#efaa74", "#f8d8bd", "#f7f5ef",
          "#d8e8f0", "#a8cfdf", "#5fa4c1", "#26769f",
        ],
        under: "#5f180d",
        over: "#114c72",
      },
    } satisfies ProductDefinition,
  },
  temperature: {
    sourceKey: "temperature_mean" as ProductKey,
    differenceProduct: {
      label: "Temperature difference",
      short_label: "Temperature difference",
      description: "Pairwise ensemble-mean temperature difference",
      units: "°C",
      baseline: null,
      legend: {
        boundaries: [-6, -4, -3, -2, -1, 1, 2, 3, 4, 6],
        colors: [
          "#243b75", "#5279ad", "#8fb4d2", "#c9dce8", "#f7f5ef",
          "#f4d0b5", "#e99461", "#cc5739", "#8f271f",
        ],
        under: "#14234f",
        over: "#63140f",
      },
    } satisfies ProductDefinition,
  },
};

const PRESENTATION_PRODUCTS: Record<ProductKey, ProductDefinition> = {
  rainfall_total: {
    label: "Weekly mean rainfall",
    short_label: "Rainfall",
    description: "Mean daily rainfall rate over each 7-day forecast week",
    units: "mm day⁻¹",
    baseline: null,
    legend: {
      boundaries: [0, 1, 2, 5, 10, 20, 40, 60],
      colors: [
        "#ffffff",
        "#b7ffb8",
        "#71f27b",
        "#24d13b",
        "#009a18",
        "#006b12",
        "#003d0c",
      ],
      under: "#ffffff",
      over: "#002807",
    },
  },
  rainfall_anomaly: {
    label: "Weekly mean rainfall anomaly",
    short_label: "Rainfall anomaly",
    description: "Difference from the model's typical rainfall for the same season and forecast lead",
    units: "mm day⁻¹",
    baseline: "Native reforecasts, 2002–2021",
    legend: {
      boundaries: [-20, -15, -10, -5, -2, 2, 5, 10, 15, 20],
      colors: [
        "#ff5200",
        "#ff8e1d",
        "#ffca59",
        "#fff4a5",
        "#ffffff",
        "#c8c8e9",
        "#8c8cbf",
        "#6464a3",
        "#3c3c87",
      ],
      under: "#d70e00",
      over: "#00001e",
    },
  },
  temperature_mean: {
    label: "Weekly mean 2 m temperature",
    short_label: "Temperature",
    description: "Mean of seven daily-mean 2 m temperature forecasts",
    units: "°C",
    baseline: null,
    legend: {
      boundaries: [10, 14, 18, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42],
      colors: [
        "#bebee2",
        "#fffacd",
        "#fff191",
        "#ffe271",
        "#ffca59",
        "#ffa635",
        "#ff8e1d",
        "#ff6a00",
        "#ff3a00",
        "#eb1800",
        "#c30400",
        "#9b0000",
        "#730000",
      ],
      under: "#9696c6",
      over: "#5f0000",
    },
  },
  temperature_anomaly: {
    label: "Weekly mean temperature anomaly",
    short_label: "Temperature anomaly",
    description: "Difference from the model's typical temperature for the same season and forecast lead",
    units: "°C",
    baseline: "Native reforecasts, 2002–2021",
    legend: {
      boundaries: [-6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6],
      colors: [
        "#383880",
        "#5a5a9c",
        "#8282b8",
        "#aaaad4",
        "#c8c8e9",
        "#dcdcf7",
        "#fffacd",
        "#ffa635",
        "#ff7605",
        "#ff5e00",
        "#ff2e00",
        "#c30400",
      ],
      under: "#10103a",
      over: "#730000",
    },
  },
  wind850_mean: {
    label: "Weekly mean 850 hPa wind",
    short_label: "850 hPa wind",
    description: "Shading is the speed of the weekly ensemble-mean wind vector; arrows are the weekly ensemble-mean U/V components",
    units: "m s⁻¹",
    baseline: null,
    legend: {
      boundaries: [0, 3, 6, 9, 12, 18, 25, 35],
      colors: [
        "#10212b",
        "#194554",
        "#1d7180",
        "#36a09b",
        "#8ac483",
        "#e1c969",
        "#e8804c",
      ],
      under: "#09171e",
      over: "#d84e43",
    },
  },
  wind850_anomaly: {
    label: "850 hPa wind anomaly",
    short_label: "850 hPa wind anomaly",
    description: "Shading shows the weekly wind-speed anomaly; the directional overlay follows the U/V vector-component anomaly",
    units: "m s⁻¹",
    baseline: "Native reforecasts, 2002–2021",
    legend: {
      boundaries: [-8, -6, -4, -2, -1, 1, 2, 4, 6, 8],
      colors: [
        "#6f321e",
        "#a8552f",
        "#d98b57",
        "#efc79f",
        "#f7f5ef",
        "#c9e2ee",
        "#83bdd4",
        "#3988b2",
        "#14567f",
      ],
      under: "#421c12",
      over: "#083653",
    },
  },
  rainfall_spread: {
    label: "Rainfall ensemble spread", short_label: "Rainfall spread",
    description: "Population standard deviation across weekly-total forecast members",
    units: "mm week⁻¹", baseline: null,
    legend: { boundaries: [0, 5, 10, 20, 40, 70, 110], colors: ["#f7fbff", "#deebf7", "#c6dbef", "#9ecae1", "#4292c6", "#08519c"], under: "#ffffff", over: "#08306b" },
  },
  temperature_spread: {
    label: "Temperature ensemble spread", short_label: "Temperature spread",
    description: "Population standard deviation across weekly-mean forecast members",
    units: "°C", baseline: null,
    legend: { boundaries: [0, 0.5, 1, 1.5, 2, 3, 5], colors: ["#fff7ec", "#fee8c8", "#fdd49e", "#fdbb84", "#e34a33", "#b30000"], under: "#ffffff", over: "#7f0000" },
  },
  rainfall_efi: undefined as never,
  temperature_efi: undefined as never,
  rainfall_sot_upper: undefined as never,
  temperature_sot_upper: undefined as never,
  temperature_sot_lower: undefined as never,
};

const PLAIN_LANGUAGE_PRODUCT_DESCRIPTIONS: Record<ProductKey, string> = {
  rainfall_total: "Shows how much rain is expected per day, averaged across each forecast week.",
  rainfall_anomaly: "Shows where a week may be wetter or drier than the model usually expects for that place and time of year.",
  temperature_mean: "Shows the expected average near-surface temperature during each forecast week.",
  temperature_anomaly: "Shows where a week may be warmer or cooler than the model usually expects for that place and time of year.",
  wind850_mean: "Shows the expected average lower-atmosphere wind speed and direction during each forecast week.",
  wind850_anomaly: "Shows where lower-atmosphere winds may be stronger, weaker or differently directed than usual.",
  rainfall_spread: "Shows the member-to-member spread in weekly rainfall totals.",
  temperature_spread: "Shows the member-to-member spread in weekly mean temperature.",
  rainfall_efi: "Compares the full rainfall ensemble distribution with the matching model climate.",
  temperature_efi: "Compares the full temperature ensemble distribution with the matching model climate.",
  rainfall_sot_upper: "Shows displacement of the wet rainfall tail relative to the model climate.",
  temperature_sot_upper: "Shows displacement of the warm temperature tail relative to the model climate.",
  temperature_sot_lower: "Shows displacement of the cold temperature tail relative to the model climate.",
};

function isWindProduct(product: ProductKey): boolean {
  return product === "wind850_mean" || product === "wind850_anomaly";
}

function productIcon(product: ProductKey): string {
  if (product === "rainfall_total") {
    return `
      <svg class="india-variable-icon india-variable-icon--rainfall" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.2 15.2h9.2a3.6 3.6 0 0 0 .4-7.2 5.3 5.3 0 0 0-9.9 1.7 2.8 2.8 0 0 0 .3 5.5Z" />
        <path d="m8 18.1-.8 1.5M12.3 18.1l-.8 1.5M16.6 18.1l-.8 1.5" />
      </svg>`;
  }
  if (product === "rainfall_anomaly") {
    return `
      <svg class="india-variable-icon india-variable-icon--rainfall-anomaly" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.2 14.2h9.2a3.6 3.6 0 0 0 .4-7.2 5.3 5.3 0 0 0-9.9 1.7 2.8 2.8 0 0 0 .3 5.5Z" />
        <path d="M8.5 20v-4m0 0-1.7 1.7M8.5 16l1.7 1.7M15.5 16v4m0 0-1.7-1.7M15.5 20l1.7-1.7" />
      </svg>`;
  }
  if (product === "temperature_mean") {
    return `
      <svg class="india-variable-icon india-variable-icon--temperature" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10 14.4V5.7a2 2 0 1 1 4 0v8.7a4 4 0 1 1-4 0Z" />
        <path d="M12 9v7.2" />
      </svg>`;
  }
  if (product === "temperature_anomaly") {
    return `
      <svg class="india-variable-icon india-variable-icon--temperature-anomaly" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.5 14.4V5.7a2 2 0 1 1 4 0v8.7a4 4 0 1 1-4 0Z" />
        <path d="M9.5 9v7.2M15.5 7h5M18 4.5v5M15.5 15.5h5" />
      </svg>`;
  }
  return `
    <svg class="india-variable-icon india-variable-icon--wind" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 8.2h10.4c2.5 0 2.5-3.7.1-3.7-1.2 0-1.9.7-2.1 1.5M4 12h14c2.7 0 2.7 4 0 4-1.2 0-2-.7-2.2-1.6M4 15.8h7" />
    </svg>`;
}

function friendlyDate(isoDate: string, includeYear = false): string {
  const calendarDate = isoDate.slice(0, 10);
  const date = new Date(`${calendarDate}T12:00:00Z`);
  if (!Number.isFinite(date.getTime())) {
    throw new Error(`Invalid forecast date: ${isoDate}`);
  }
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    ...(includeYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(date);
}

function displayWeek(week: ForecastWeek, product: ProductKey): ForecastWeek {
  if (product !== "rainfall_total") return week;
  const rainfall = week.fields.rainfall_total;
  if (!rainfall) return week;
  return {
    ...week,
    fields: {
      ...week.fields,
      rainfall_total: rainfall.map((value) => value === null ? null : value / 7),
    },
  };
}

function renderInitializationComparison(
  container: HTMLElement,
  comparison: InitializationComparisonData,
  forecasts: Partial<Record<InitialConditionSourceId, ForecastData>>,
  geography: AppData["indiaGeography"],
): void {
  if (!geography || !comparison.pairs.length) return;
  const sourceOrder = INITIAL_CONDITION_SOURCE_DISPLAY_ORDER.filter(
    (source) => source in comparison.sources && forecasts[source],
  );
  if (sourceOrder.length < 2) return;
  const host = container.querySelector<HTMLDivElement>("#india-comparison-explorer");
  if (!host) return;
  let weekIndex = 0;
  let variable: keyof typeof COMPARISON_PRODUCTS = "rainfall";

  host.innerHTML = `
    <div class="india-comparison-toolbar">
      <div role="group" aria-label="Comparison variable">
        <button type="button" data-variable="rainfall" class="is-active" aria-pressed="true">Rainfall</button>
        <button type="button" data-variable="temperature" aria-pressed="false">Temperature</button>
      </div>
      <label>Forecast week
        <select aria-label="Comparison forecast week">
          ${Array.from({ length: 6 }, (_, index) => `<option value="${index}">Week ${index + 1}</option>`).join("")}
        </select>
      </label>
    </div>
    <h3>Ensemble means</h3>
    <div class="india-comparison-grid" data-comparison-sources></div>
    <h3>Pairwise differences and India metrics</h3>
    <div class="india-comparison-grid" data-comparison-pairs></div>
  `;
  const sourceGrid = host.querySelector<HTMLDivElement>("[data-comparison-sources]")!;
  const pairGrid = host.querySelector<HTMLDivElement>("[data-comparison-pairs]")!;

  const render = (): void => {
    const definition = COMPARISON_PRODUCTS[variable];
    sourceGrid.replaceChildren();
    sourceOrder.forEach((sourceId) => {
      const sourceForecast = forecasts[sourceId]!;
      const week = displayWeek(sourceForecast.weeks[weekIndex], definition.sourceKey);
      const panel = document.createElement("article");
      panel.className = "india-comparison-panel";
      panel.innerHTML = `<h4>${sourceForecast.issue.initial_condition_source.short_label}</h4><div class="india-map-frame"></div>`;
      sourceGrid.append(panel);
      new ForecastMap(
        panel.querySelector<HTMLDivElement>(".india-map-frame")!,
        sourceForecast,
        geography,
      ).render(
        definition.sourceKey,
        week,
        PRESENTATION_PRODUCTS[definition.sourceKey],
      );
    });

    pairGrid.replaceChildren();
    comparison.pairs.forEach((pair) => {
      const comparisonWeek = pair.weeks[weekIndex];
      const metrics = comparisonWeek[variable];
      const base = forecasts[pair.left_source_id]!;
      const fieldWeek: ForecastWeek = {
        week: comparisonWeek.week,
        valid_start: comparisonWeek.valid_start,
        valid_end: comparisonWeek.valid_end,
        fields: { [definition.sourceKey]: metrics.difference_field },
        summary: {},
      };
      const panel = document.createElement("article");
      panel.className = "india-comparison-panel";
      panel.innerHTML = `
        <h4>${pair.label}</h4>
        <div class="india-map-frame"></div>
        <dl>
          <div><dt>India mean</dt><dd>${metrics.area_weighted_mean_difference >= 0 ? "+" : ""}${metrics.area_weighted_mean_difference.toFixed(2)} ${definition.differenceProduct.units}</dd></div>
          <div><dt>Mean absolute difference</dt><dd>${metrics.mean_absolute_difference.toFixed(2)}</dd></div>
          <div><dt>Pattern correlation</dt><dd>${metrics.ensemble_mean_pattern_correlation.toFixed(2)}</dd></div>
          <div><dt>Spread · left / right</dt><dd>${metrics.left_mean_spread.toFixed(2)} / ${metrics.right_mean_spread.toFixed(2)}</dd></div>
        </dl>
      `;
      pairGrid.append(panel);
      new ForecastMap(
        panel.querySelector<HTMLDivElement>(".india-map-frame")!,
        base,
        geography,
      ).render(definition.sourceKey, fieldWeek, definition.differenceProduct);
    });
  };

  host.querySelectorAll<HTMLButtonElement>("[data-variable]").forEach((button) => {
    button.addEventListener("click", () => {
      variable = button.dataset.variable as keyof typeof COMPARISON_PRODUCTS;
      host.querySelectorAll<HTMLButtonElement>("[data-variable]").forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("is-active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      render();
    });
  });
  host.querySelector<HTMLSelectElement>("select")!.addEventListener("change", (event) => {
    weekIndex = Number((event.currentTarget as HTMLSelectElement).value);
    render();
  });
  render();
}

export function renderForecastPage(
  container: HTMLElement,
  data: AppData,
): (() => void) | undefined {
  const {
    forecast,
    validation,
    index,
    indiaGeography,
    domainCatalog,
    activeDomain,
  } = data;
  if (!forecast || !validation || !index || !indiaGeography) {
    container.innerHTML = `
      <section class="blocked-state">
        <span class="eyebrow">Forecast data unavailable</span>
        <h1>The selected domain forecast package could not be loaded.</h1>
        <p>No partial map has been shown.</p>
      </section>
    `;
    return;
  }
  const activeForecast = forecast;
  const activeGeography = indiaGeography;
  if (!validation.presentation_allowed) {
    container.innerHTML = `
      <section class="blocked-state">
        <span class="eyebrow">Publication gate closed</span>
        <h1>This forecast is not available for presentation.</h1>
        <p>A scientific or publication check failed, so no partial map is shown.</p>
      </section>
    `;
    return;
  }
  const sourceId = forecast.issue.initial_condition_source.id;
  const source = index.initial_condition_sources.find(
    (candidate) => candidate.id === sourceId,
  );
  if (!source) {
    container.innerHTML = `
      <section class="blocked-state">
        <span class="eyebrow">Run unavailable</span>
        <h1>The selected initialization source is not registered.</h1>
        <p>No partial map has been shown.</p>
      </section>
    `;
    return;
  }
  const currentIssueId = forecast.issue.initialization.slice(0, 10).replaceAll("-", "");
  const catalogIssue = source.issues.find((issue) => issue.id === currentIssueId);
  if (!catalogIssue) {
    throw new Error("The loaded forecast is not present in the issue catalogue");
  }
  const isCurrent = issueIsCurrent(index, source, catalogIssue);
  const availableProducts = productKeysForForecast(
    forecast,
    catalogIssue.available_products,
  );
  const availableExtremeProducts = extremeProductKeysForForecast(
    forecast,
    catalogIssue.available_products,
  );
  if (availableProducts.length === 0) {
    container.innerHTML = `
      <section class="blocked-state">
        <span class="eyebrow">Products unavailable</span>
        <h1>This issue has no publishable fields for the selected domain.</h1>
        <p>The catalogue remains available, but no partial map has been shown.</p>
        <a href="./#archive">Return to the forecast archive</a>
      </section>
    `;
    return;
  }
  const defaultProduct: ProductKey = availableProducts.includes("rainfall_anomaly")
    ? "rainfall_anomaly"
    : availableProducts[0];
  const sourceLink = (id: InitialConditionSourceId, issue: string): string =>
    `./?source=${id}&issue=${issue}${activeDomain && activeDomain.id !== "india" ? `&domain=${activeDomain.id}` : ""}#india`;
  const currentSelection = currentForecast(index);
  const currentForecastLink = currentSelection
    ? sourceLink(currentSelection.source.id, currentSelection.issue.id)
    : "./#india";
  const sourceLatestIssue = defaultIssueForSource(index, source);
  const isSourceLatest = sourceLatestIssue?.id === catalogIssue.id;
  const matchedSource = index.initial_condition_sources.find(
    (candidate) =>
      candidate.id !== sourceId &&
      candidate.issues.some((issue) => issue.id === currentIssueId),
  );
  const pdfPath = forecast.issue.downloads?.domain_pdf ??
    forecast.issue.downloads?.india_pdf;
  const pdfReady = typeof pdfPath === "string" && pdfPath.endsWith(".pdf");
  const pdfChecksum = forecast.issue.downloads?.domain_pdf_sha256 ??
    forecast.issue.downloads?.india_pdf_sha256;
  const pdfVersion = typeof pdfChecksum === "string" && pdfChecksum.length >= 12
    ? pdfChecksum.slice(0, 12)
    : encodeURIComponent(forecast.generated_at);
  const pdfUrl = pdfReady
    ? `./${pdfPath}?v=${pdfVersion}`
    : "";
  const initializationComparison = data.initializationComparison;
  const validFrom = forecast.weeks.at(0)?.valid_start ??
    forecast.issue.initialization.slice(0, 10);
  const validThrough = forecast.weeks.at(-1)?.valid_end ?? "";
  const issueSelectionLabel = isCurrent
    ? "Main forecast"
    : isSourceLatest
      ? sourceId === "era5"
        ? "Latest delayed reference"
        : "Latest validated source issue"
      : "Selected archive issue";
  const archiveTitle = sourceId === "era5" && isSourceLatest
    ? "Latest delayed reference—not the main forecast"
    : sourceId === "gfs" && isSourceLatest
      ? "Latest GFS proxy—not the main forecast"
      : "You are viewing an archived issue";
  const archiveMessage = sourceId === "era5" && isSourceLatest
    ? "This is ERA5's latest validated delayed reference. Source initialization dates are independent, and ERA5 normally arrives 5–7 days after real time."
    : sourceId === "gfs" && isSourceLatest
      ? "This is the latest secondary GFS-proxy issue. IFS initialization is the dashboard's main experimental forecast; source initialization dates can differ."
      : catalogIssue.members < 100
        ? "This limited-member experiment is preserved for research transparency and must not be compared as a full operational ensemble."
        : "This older issue is retained in the archive. The main page points to the latest validated IFS-initialized issue.";
  const archiveBanner = !isCurrent
    ? `
      <aside class="india-archive-banner" aria-label="Non-current forecast notice">
        <div>
          <strong>${archiveTitle}</strong>
          <p>${archiveMessage}</p>
        </div>
        <a href="${currentForecastLink}">Return to main forecast →</a>
      </aside>
    `
    : "";
  const comparisonCard = activeDomain?.id !== "india"
    ? ""
    : initializationComparison
    ? `
      <section class="india-ic-comparison" aria-label="Matched initialization-source comparison">
        <div>
          <span>Matched initialization sensitivity</span>
          <strong>${Object.keys(initializationComparison.sources).map((id) => id.toUpperCase()).join(" · ")}</strong>
          <p>${initializationComparison.interpretation}</p>
        </div>
        <div id="india-comparison-explorer"></div>
      </section>`
    : "";
  const displaySources = sourcesForDisplay(index);
  const preferredIssues = new Map(
    displaySources.map((candidate) => [
      candidate.id,
      defaultIssueForSource(index, candidate),
    ] as const),
  );
  const latestSourceDates = displaySources
    .map((candidate) => {
      const preferred = preferredIssues.get(candidate.id);
      return preferred
        ? `<span><strong>${candidate.short_label}</strong><time datetime="${preferred.initialization.slice(0, 10)}">${friendlyDate(preferred.initialization, true)}</time></span>`
        : "";
    })
    .filter(Boolean)
    .join("");

  container.innerHTML = `
    <section class="india-sheet" data-product="${defaultProduct}">
      <header class="india-sheet__header">
        <div class="india-hero-copy">
          <span class="india-sheet__brand">INDIA SUBSEASONAL FORECAST</span>
          <h1>India six-week forecast maps</h1>
          <dl class="india-forecast-window" aria-label="Forecast timing">
            <div><dt>Forecast run</dt><dd><time datetime="${forecast.issue.initialization.slice(0, 10)}">${friendlyDate(forecast.issue.initialization.slice(0, 10), true)}</time> · 00 UTC</dd></div>
            <div><dt>Maps cover</dt><dd><time datetime="${validFrom}">${friendlyDate(validFrom)}</time> – <time datetime="${validThrough}">${friendlyDate(validThrough, true)}</time></dd></div>
            <div><dt>Available</dt><dd>Weeks 1–6</dd></div>
          </dl>
        </div>
        <a class="india-hero-briefing" href="./#briefing">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M7 2.75h6.6L18.25 7.4V21.25H7z" />
            <path d="M13.5 2.75V7.5h4.75M9.75 12h5.5M9.75 15.5h5.5" />
          </svg>
          <span><strong>Read forecast briefing</strong><small>Plain-language summary and full report</small></span>
          <i aria-hidden="true">→</i>
        </a>
      </header>

      ${archiveBanner}

      <div class="india-map-workspace">
        <div class="india-view-selector" role="group" aria-label="Forecast view">
          <button type="button" data-forecast-view="mean" class="is-active" aria-pressed="true">Mean</button>
          <button type="button" data-forecast-view="probability" aria-pressed="false">Probability</button>
          <button type="button" data-forecast-view="spread" aria-pressed="false">Ensemble spread</button>
          <button type="button" data-forecast-view="extremes" aria-pressed="false">Extremes</button>
        </div>
        <div class="india-toolbar">
          <div class="india-toolbar__variables">
            <div class="india-product-tabs" id="india-product-tabs" role="group" aria-label="Forecast variable"></div>
            <div class="india-probability-variable-tabs" id="india-probability-variable-tabs" role="group" aria-label="Probabilistic forecast variable" hidden>
              <button type="button" data-probability-variable="rainfall" class="is-active" aria-pressed="true">Rainfall</button>
              <button type="button" data-probability-variable="temperature" aria-pressed="false">Temperature</button>
            </div>
          </div>
          <div class="india-view-controls">
            <label class="india-probability-product" id="india-probability-product" hidden>
              <span>Product</span>
              <select aria-label="Probability product">
                <option value="most_likely">Most likely tercile</option>
                <option value="below_normal">Below-normal tercile probability</option>
                <option value="near_normal">Near-normal tercile probability</option>
                <option value="above_normal">Above-normal tercile probability</option>
                <option value="category_margin">Leading-category margin</option>
                <optgroup label="Requires additional member summaries">
                  <option disabled>Threshold exceedance probability</option>
                </optgroup>
              </select>
            </label>
            <label class="india-distribution-product" id="india-distribution-product" hidden>
              <span>Distribution map</span>
              <select aria-label="Ensemble distribution map product">
                <option value="spread">P90 − P10 spread</option>
                <option value="p10">P10 lower outcome</option>
                <option value="p50">Median outcome</option>
                <option value="p90">P90 upper outcome</option>
              </select>
            </label>
            <label class="india-extreme-product" id="india-extreme-product" hidden>
              <span>Extreme product</span>
              <select aria-label="Extreme forecast product">
                <option value="efi">Extreme Forecast Index (EFI)</option>
                <option value="sot_upper">Upper-tail Shift of Tails</option>
                <option value="sot_lower">Lower-tail Shift of Tails</option>
              </select>
            </label>
            <label class="india-probability-extent" id="india-probability-extent" hidden>
              <span>Extent</span>
              <select aria-label="Probabilistic map extent">
                <option value="india">India</option>
                <option value="regional">Regional grid (60–99°E)</option>
              </select>
            </label>
            <div class="india-wind-mode" id="india-wind-mode" role="group" aria-label="Wind direction display" hidden>
              <span>Wind display</span>
              <button type="button" data-wind-mode="streamlines" class="is-active">Streamlines</button>
              <button type="button" data-wind-mode="arrows">Arrows</button>
            </div>
            <label class="india-range-select">
              <span>Forecast window</span>
              <select id="india-range-select" aria-label="Displayed forecast weeks">
                <option value="0">Weeks 1–4</option>
                <option value="2">Weeks 3–6</option>
              </select>
            </label>
          </div>
        </div>

        <p class="ops-visually-hidden" id="india-product-status" aria-live="polite" aria-atomic="true"></p>

        <div class="india-visualization" id="india-visualization">
          <div class="india-visualization__main">
            <div class="india-panel-grid" id="india-panel-grid" aria-label="${activeDomain?.label ?? "India"} forecast maps"></div>
            <div class="india-map-key">
              <div class="india-shared-legend" id="india-shared-legend"></div>
              <section class="india-map-guide" aria-labelledby="india-map-guide-title">
                <span>How to read these maps</span>
                <h2 id="india-map-guide-title" class="india-selected-product">${PRESENTATION_PRODUCTS[defaultProduct].label}</h2>
                <p><span id="india-product-explanation">${PLAIN_LANGUAGE_PRODUCT_DESCRIPTIONS[defaultProduct]}</span> Hover, tap, or focus a map for local values. Click a supported cell for all-week detail.</p>
                <p class="india-visual-note" id="india-visual-note"></p>
                <details class="india-probability-definition" id="india-probability-definition" hidden>
                  <summary>How terciles are defined</summary>
                  <p>Below normal means below the lower-tercile threshold; near normal includes both thresholds; above normal means above the upper-tercile threshold. These are not comparisons with the mean or median.</p>
                </details>
              </section>
            </div>
          </div>
          <div class="probability-location-host" id="probability-location-host" hidden></div>
        </div>
      </div>

      <section class="india-forecast-details" aria-labelledby="india-forecast-details-title">
        <header class="india-forecast-details__header">
          <h2 id="india-forecast-details-title">Sources and downloads</h2>
          <p>This experimental AI ensemble can start from different datasets. IFS is the main forecast, GFS is a secondary proxy, and ERA5 is a delayed research reference.</p>
        </header>
        ${domainCatalog && domainCatalog.domains.length > 1 ? `
          <label class="india-domain-select">Forecast domain
            <select aria-label="Forecast domain">
              ${domainCatalog.domains.map((domain) => `<option value="${domain.id}" ${domain.id === activeDomain?.id ? "selected" : ""}>${domain.label}</option>`).join("")}
            </select>
          </label>
        ` : ""}
      <section class="india-run-console" aria-label="Forecast sources and files">
        <div class="india-run-console__heading">
          <div>
            <span>${issueSelectionLabel}</span>
            <strong>${forecast.issue.initial_condition_source.label}</strong>
          </div>
          <span class="india-experimental">Experimental AI ensemble</span>
          <details class="india-source-guide">
            <summary
              aria-label="Explain IFS, GFS, and ERA5 sources"
              title="Explain forecast sources"
            >
              <span class="india-source-guide__icon" aria-hidden="true">i</span>
              <span>About sources</span>
            </summary>
            <div class="india-source-guide__panel" id="india-source-guide">
              <strong>One forecast system, three input sources</strong>
              <p>These labels describe how the same experimental forecasting system is initialized.</p>
              <dl>
                <div><dt>IFS</dt><dd>ECMWF Integrated Forecasting System inputs; main experimental guidance.</dd></div>
                <div><dt>GFS</dt><dd>Global Forecast System inputs; secondary near-real-time proxy.</dd></div>
                <div><dt>ERA5</dt><dd>Delayed ECMWF reanalysis reference for controlled comparisons, not current guidance.</dd></div>
              </dl>
            </div>
          </details>
        </div>
        <div class="india-source-selection">
          <div class="india-source-tabs" role="navigation" aria-label="Initial-condition source" aria-describedby="india-source-guide india-source-date-notice">
            ${displaySources.map((candidate) => {
              const preferred = preferredIssues.get(candidate.id);
              if (!preferred) return `<span class="is-pending" aria-disabled="true"><span>${candidate.short_label}</span><small>Pilot pending</small></span>`;
              return `
              <a href="${sourceLink(candidate.id, preferred.id)}" class="${candidate.id === sourceId ? "is-active" : ""}" ${candidate.id === sourceId ? "aria-current=\"page\"" : ""}>
                <span>${candidate.short_label}</span>
                <small>${candidate.id === index.default_source ? "Main forecast" : candidate.category === "operational_proxy" ? "Secondary proxy" : "Delayed reference"}</small>
              </a>
            `;}).join("")}
          </div>
          <div class="india-source-date-notice" id="india-source-date-notice" role="note">
            <span>Latest validated runs</span>
            <div>${latestSourceDates}</div>
            <small>Sources update on different dates. Selecting one opens its latest run.</small>
          </div>
          ${matchedSource ? `<a class="india-matched-run" href="${sourceLink(matchedSource.id, currentIssueId)}">Compare this ${friendlyDate(forecast.issue.initialization.slice(0, 10), true)} run with ${matchedSource.short_label} inputs →</a>` : ""}
        </div>
        <div class="india-run-actions" aria-label="Forecast downloads">
          <div class="india-run-actions__secondary">
            ${pdfReady
              ? `<a class="india-pdf-download-secondary" href="${pdfUrl}" target="_blank" rel="noopener noreferrer" type="application/pdf">Open forecast PDF ↗</a><a class="india-pdf-download-tertiary" href="${pdfUrl}" download type="application/pdf">Download PDF ↓</a>`
              : `<button class="india-pdf-download-secondary" type="button" disabled>Forecast PDF preparing</button>`}
            <a class="india-archive-action" href="./#archive">Browse archive →</a>
          </div>
        </div>
      </section>
      </section>

      ${comparisonCard}
      <footer class="india-sheet__footer">
        <p id="india-baseline-note"></p>
        <p class="india-research-notice"><strong>Experimental research guidance</strong><span>Not an operational weather forecast or warning.</span></p>
      </footer>
    </section>
  `;


  type ForecastView = "mean" | "probability" | "spread" | "extremes";
  type ExtremeProduct = "efi" | "sot_upper" | "sot_lower";
  let selectedProduct: ProductKey = defaultProduct;
  let selectedView: ForecastView = "mean";
  let selectedProbabilityProduct: ProbabilityMapProduct = "most_likely";
  let selectedDistributionProduct: DistributionMapProduct = "spread";
  let selectedExtremeProduct: ExtremeProduct = "efi";
  let selectedProbabilityVariable: ProbabilisticVariable =
    defaultProduct.startsWith("temperature") ? "temperature" : "rainfall";
  let selectedProbabilityExtent: "india" | "regional" = "regional";
  let selectedLocation: ForecastGridSelection | undefined;
  let regionalOutlook: RegionalOutlookData | undefined;
  let regionalOutlookPromise: Promise<RegionalOutlookData> | undefined;
  let rangeStart = 0;
  let windRenderingMode: WindRenderingMode = "streamlines";
  let requestGeneration = 0;
  const requestController = new AbortController();
  const productTabs = container.querySelector<HTMLDivElement>("#india-product-tabs")!;
  const probabilityVariableTabs = container.querySelector<HTMLDivElement>(
    "#india-probability-variable-tabs",
  )!;
  const panelGrid = container.querySelector<HTMLDivElement>("#india-panel-grid")!;
  const panelHost = container.querySelector<HTMLDivElement>(
    "#probability-location-host",
  )!;
  const windModeControl = container.querySelector<HTMLDivElement>("#india-wind-mode")!;
  const rangeSelect = container.querySelector<HTMLSelectElement>("#india-range-select")!;
  const probabilityProductControl = container.querySelector<HTMLLabelElement>(
    "#india-probability-product",
  )!;
  const probabilityProductSelect = probabilityProductControl.querySelector("select")!;
  const distributionProductControl = container.querySelector<HTMLLabelElement>(
    "#india-distribution-product",
  )!;
  const distributionProductSelect = distributionProductControl.querySelector("select")!;
  const extremeProductControl = container.querySelector<HTMLLabelElement>(
    "#india-extreme-product",
  )!;
  const extremeProductSelect = extremeProductControl.querySelector("select")!;
  const probabilityExtentControl = container.querySelector<HTMLLabelElement>(
    "#india-probability-extent",
  )!;
  const probabilityExtentSelect = probabilityExtentControl.querySelector("select")!;
  const probabilityDefinition = container.querySelector<HTMLDetailsElement>(
    "#india-probability-definition",
  )!;
  const productStatus = container.querySelector<HTMLElement>("#india-product-status")!;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const probabilisticAvailable =
    activeDomain?.id === "india" &&
    issueHasRegionalOutlook(index, catalogIssue, forecast);
  let panelAnimationTimer: number | undefined;
  let productIndicatorFrame: number | undefined;

  container.querySelectorAll<HTMLButtonElement>("[data-forecast-view]")
    .forEach((button) => {
      if (
        button.dataset.forecastView !== "mean" &&
        button.dataset.forecastView !== "extremes" &&
        !probabilisticAvailable
      ) {
        button.disabled = true;
        button.title = "A complete ensemble and matched model climatology are required.";
      }
      button.addEventListener("click", () => {
        const view = button.dataset.forecastView as ForecastView;
        void selectView(view);
      });
    });

  container.querySelector<HTMLSelectElement>(".india-domain-select select")
    ?.addEventListener("change", (event) => {
      const parameters = new URLSearchParams(window.location.search);
      const domainId = (event.currentTarget as HTMLSelectElement).value;
      if (domainId === domainCatalog?.default_domain) parameters.delete("domain");
      else parameters.set("domain", domainId);
      parameters.delete("source");
      parameters.delete("issue");
      window.location.assign(`./?${parameters.toString()}#india`);
    });

  availableProducts.forEach((productKey) => {
    const product = PRESENTATION_PRODUCTS[productKey];
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.product = productKey;
    button.innerHTML = `<span class="india-variable-mark">${productIcon(productKey)}</span><strong>${product.short_label}</strong>`;
    button.addEventListener("click", () => {
      selectedProduct = productKey;
      if (productKey.startsWith("rainfall")) {
        selectedProbabilityVariable = "rainfall";
      }
      if (productKey.startsWith("temperature")) {
        selectedProbabilityVariable = "temperature";
      }
      refreshPresentation(`Showing ${product.label}.`);
    });
    productTabs.append(button);
  });
  const productIndicator = document.createElement("span");
  productIndicator.className = "india-product-indicator";
  productIndicator.setAttribute("aria-hidden", "true");
  productTabs.append(productIndicator);
  window.addEventListener("resize", positionProductIndicator);

  probabilityVariableTabs
    .querySelectorAll<HTMLButtonElement>("[data-probability-variable]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        selectedProbabilityVariable =
          button.dataset.probabilityVariable as ProbabilisticVariable;
        const preferAnomaly = selectedProduct.endsWith("_anomaly");
        const meanCandidates: ProductKey[] = selectedProbabilityVariable === "rainfall"
          ? preferAnomaly
            ? ["rainfall_anomaly", "rainfall_total"]
            : ["rainfall_total", "rainfall_anomaly"]
          : preferAnomaly
            ? ["temperature_anomaly", "temperature_mean"]
            : ["temperature_mean", "temperature_anomaly"];
        const matchingMeanProduct = meanCandidates.find((candidate) =>
          availableProducts.includes(candidate)
        );
        if (matchingMeanProduct) selectedProduct = matchingMeanProduct;
        if (
          selectedProbabilityVariable === "rainfall" &&
          selectedExtremeProduct === "sot_lower"
        ) {
          selectedExtremeProduct = "efi";
        }
        refreshPresentation(`Showing ${selectedProbabilityVariable} ${selectedView}.`);
      });
    });

  probabilityProductSelect.addEventListener("change", () => {
    selectedProbabilityProduct =
      probabilityProductSelect.value as ProbabilityMapProduct;
    refreshPresentation("Showing selected tercile probability product.");
  });

  distributionProductSelect.addEventListener("change", () => {
    selectedDistributionProduct =
      distributionProductSelect.value as DistributionMapProduct;
    refreshPresentation("Showing selected ensemble distribution product.");
  });

  extremeProductSelect.addEventListener("change", () => {
    selectedExtremeProduct = extremeProductSelect.value as ExtremeProduct;
    refreshPresentation("Showing selected extreme forecast product.");
  });

  probabilityExtentSelect.addEventListener("change", () => {
    selectedProbabilityExtent = probabilityExtentSelect.value as "india" | "regional";
    if (selectedProbabilityExtent === "india" && selectedLocation) {
      const mask = activeForecast.grid.india_mask ??
        activeForecast.grid.support_mask ?? [];
      const index = selectedLocation.latitude_index * activeForecast.grid.longitude.length +
        selectedLocation.longitude_index;
      if (!(mask[index] ?? false)) selectedLocation = undefined;
    }
    refreshPresentation(
      selectedProbabilityExtent === "regional"
        ? `Showing the full available regional ${selectedView} grid.`
        : `Showing ${selectedView} over India.`,
    );
  });

  rangeSelect.addEventListener("change", () => {
    rangeStart = Number(rangeSelect.value);
    refreshPresentation(`Showing Weeks ${rangeStart + 1}–${rangeStart + 4}.`);
  });

  windModeControl
    .querySelectorAll<HTMLButtonElement>("button[data-wind-mode]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        windRenderingMode = button.dataset.windMode as WindRenderingMode;
        refreshPresentation(`Showing wind as ${windRenderingMode}.`);
      });
    });

  function positionProductIndicator(): void {
    if (productIndicatorFrame !== undefined) {
      window.cancelAnimationFrame(productIndicatorFrame);
    }
    productIndicatorFrame = window.requestAnimationFrame(() => {
      const activeButton = productTabs.querySelector<HTMLButtonElement>(
        "button.is-active",
      );
      if (!activeButton || productTabs.hidden) return;
      productTabs.style.setProperty(
        "--product-indicator-x",
        `${activeButton.offsetLeft}px`,
      );
      productTabs.style.setProperty(
        "--product-indicator-y",
        `${activeButton.offsetTop}px`,
      );
      productTabs.style.setProperty(
        "--product-indicator-width",
        `${activeButton.offsetWidth}px`,
      );
      productTabs.style.setProperty(
        "--product-indicator-height",
        `${activeButton.offsetHeight}px`,
      );
      productTabs.classList.add("has-positioned-indicator");
      productIndicatorFrame = undefined;
    });
  }

  async function loadRegionalOutlook(): Promise<RegionalOutlookData> {
    if (!catalogIssue!.regional_outlook) {
      throw new Error("No member-derived summary package is published for this issue.");
    }
    if (!regionalOutlookPromise) {
      const path = checksumVersionedPath(
        `./data/${catalogIssue!.regional_outlook}`,
        issueChecksum(catalogIssue!, "regional_outlook"),
      );
      regionalOutlookPromise = fetch(path, { signal: requestController.signal })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Member-derived summary returned ${response.status}.`);
          }
          const outlook = await response.json() as RegionalOutlookData;
          if (
            outlook.issue.initialization !== activeForecast.issue.initialization ||
            outlook.issue.source_id !== sourceId
          ) {
            throw new Error("Member-derived summary does not match this forecast issue.");
          }
          return outlook;
        });
    }
    return regionalOutlookPromise;
  }

  function extremeProductKey(
    variable = selectedProbabilityVariable,
    product = selectedExtremeProduct,
  ): ProductKey {
    if (product === "efi") return `${variable}_efi` as ProductKey;
    if (product === "sot_upper") return `${variable}_sot_upper` as ProductKey;
    return "temperature_sot_lower";
  }

  async function selectView(view: ForecastView): Promise<void> {
    if (view !== "mean" && view !== "extremes" && !probabilisticAvailable) return;
    selectedView = view;
    requestGeneration += 1;
    const generation = requestGeneration;
    updateControls();
    if (view === "mean" || view === "extremes") {
      update(!reducedMotion.matches);
      return;
    }
    if (!regionalOutlook) {
      panelGrid.innerHTML = `
        <div class="probability-loading-state" role="status">
          <span class="probability-loading-state__spinner" aria-hidden="true"></span>
          <strong>Loading member-derived summaries…</strong>
        </div>
      `;
      try {
        const loaded = await loadRegionalOutlook();
        if (generation !== requestGeneration || selectedView === "mean") return;
        regionalOutlook = loaded;
      } catch (error) {
        if (requestController.signal.aborted || generation !== requestGeneration) return;
        const message = error instanceof Error ? error.message : "Unknown data error";
        panelGrid.innerHTML = `
          <div class="probability-unavailable-state" role="alert">
            <strong>Probabilistic fields unavailable</strong>
            <p>${message} The ensemble-mean maps remain available.</p>
          </div>
        `;
        return;
      }
    }
    update(!reducedMotion.matches);
  }

  function updateControls(): void {
    container.querySelectorAll<HTMLButtonElement>("[data-forecast-view]")
      .forEach((button) => {
        const active = button.dataset.forecastView === selectedView;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    productTabs.hidden = selectedView !== "mean";
    probabilityVariableTabs.hidden = selectedView === "mean";
    probabilityProductControl.hidden = selectedView !== "probability";
    distributionProductControl.hidden = selectedView !== "spread";
    extremeProductControl.hidden = selectedView !== "extremes";
    probabilityExtentControl.hidden = selectedView === "mean" || selectedView === "extremes";
    probabilityDefinition.hidden = selectedView !== "probability";
    probabilityProductSelect.value = selectedProbabilityProduct;
    distributionProductSelect.value = selectedDistributionProduct;
    extremeProductSelect.value = selectedExtremeProduct;
    const lowerTailOption = extremeProductSelect.querySelector<HTMLOptionElement>(
      'option[value="sot_lower"]',
    );
    if (lowerTailOption) {
      lowerTailOption.hidden = selectedProbabilityVariable === "rainfall";
      lowerTailOption.disabled = selectedProbabilityVariable === "rainfall";
    }
    probabilityExtentSelect.value = selectedProbabilityExtent;
    probabilityVariableTabs
      .querySelectorAll<HTMLButtonElement>("[data-probability-variable]")
      .forEach((button) => {
        const active =
          button.dataset.probabilityVariable === selectedProbabilityVariable;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    windModeControl.hidden =
      selectedView !== "mean" || !isWindProduct(selectedProduct);
  }

  function refreshPresentation(statusMessage: string): void {
    productStatus.textContent = statusMessage;
    if (!reducedMotion.matches && typeof document.startViewTransition === "function") {
      document.startViewTransition(() => update(false));
      return;
    }
    update(!reducedMotion.matches);
  }

  function renderPanel(): void {
    if (!selectedLocation) {
      panelHost.hidden = true;
      panelHost.replaceChildren();
      return;
    }
    if (selectedView === "extremes" && activeForecast.extreme_definition) {
      renderExtremeForecastPanel(
        panelHost,
        activeForecast,
        selectedProbabilityVariable,
        selectedLocation,
        (variable) => {
          selectedProbabilityVariable = variable;
          if (variable === "rainfall" && selectedExtremeProduct === "sot_lower") {
            selectedExtremeProduct = "efi";
          }
          refreshPresentation(`Showing ${variable} extremes.`);
        },
        (week) => {
          selectedLocation = { ...selectedLocation!, week };
          renderPanel();
        },
        closePanel,
      );
      return;
    }
    if (!regionalOutlook) {
      panelHost.hidden = false;
      panelHost.innerHTML = `
        <aside class="probability-location-panel">
          <header class="probability-location-panel__header">
            <div><span>Selected native grid cell</span><h2>${selectedLocation.latitude.toFixed(1)}°N · ${selectedLocation.longitude.toFixed(1)}°E</h2></div>
            <button type="button" class="probability-panel__close" aria-label="Close location details">×</button>
          </header>
          <div class="probability-panel__unavailable" role="note">
            <strong>Member distribution unavailable</strong>
            <p>This issue has no compatible member-derived summary package. No distribution has been reconstructed from the ensemble mean.</p>
          </div>
        </aside>
      `;
      panelHost.querySelector<HTMLButtonElement>(".probability-panel__close")
        ?.addEventListener("click", closePanel);
      return;
    }
    renderLocationForecastPanel(
      panelHost,
      regionalOutlook,
      selectedProbabilityVariable,
      selectedLocation,
      closePanel,
    );
  }

  function closePanel(): void {
    selectedLocation = undefined;
    panelHost.hidden = true;
    update(false);
    panelGrid.querySelector<SVGSVGElement>("svg")?.focus({ preventScroll: true });
  }

  function handleLocationSelection(selection: ForecastGridSelection): void {
    selectedLocation = selection;
    if (selectedView === "extremes") {
      update(false);
      return;
    }
    if (regionalOutlook) {
      update(false);
      return;
    }
    renderPanel();
    if (!probabilisticAvailable) return;
    const generation = ++requestGeneration;
    void loadRegionalOutlook()
      .then((loaded) => {
        if (generation !== requestGeneration || !selectedLocation) return;
        regionalOutlook = loaded;
        update(false);
      })
      .catch(() => {
        if (!requestController.signal.aborted) renderPanel();
      });
  }

  function makeMapPanels(
    weeks: ForecastWeek[],
    renderMap: (
      frame: HTMLDivElement,
      week: ForecastWeek,
    ) => void,
  ): void {
    panelGrid.replaceChildren();
    weeks.forEach((week) => {
      const panel = document.createElement("article");
      panel.className = "india-map-panel";
      panel.innerHTML = `
        <h2>
          <strong>Week ${week.week}</strong>
          <span class="india-map-panel__period"><time datetime="${week.valid_start}">${friendlyDate(week.valid_start)}</time> – <time datetime="${week.valid_end}">${friendlyDate(week.valid_end, true)}</time></span>
        </h2>
        <div class="india-map-frame"></div>
      `;
      panelGrid.append(panel);
      renderMap(panel.querySelector<HTMLDivElement>(".india-map-frame")!, week);
    });
  }

  function probabilityLegend(): string {
    if (selectedView === "spread") {
      if (selectedDistributionProduct !== "spread") {
        const percentile = selectedDistributionProduct === "p10"
          ? "P10 lower outcome"
          : selectedDistributionProduct === "p50"
            ? "Median outcome (P50)"
            : "P90 upper outcome";
        const ticks = selectedProbabilityVariable === "rainfall"
          ? [["0", 0], ["5", 8.33], ["10", 16.67], ["20", 33.33], ["40", 66.67], ["≥60", 100]]
          : [["10", 0], ["18", 25], ["26", 50], ["34", 75], ["≥42", 100]];
        return `
          <div class="probability-legend">
            <strong>${percentile}</strong>
            <div class="probability-legend__percentile-gradient is-${selectedProbabilityVariable}" aria-hidden="true"></div>
            <div class="probability-legend__percentile-ticks">
              ${ticks.map(([label, position]) => `<span style="left:${position}%">${label}</span>`).join("")}
            </div>
            <p>Fixed ${selectedProbabilityVariable === "rainfall" ? "mm day⁻¹" : "°C"} scale across weeks. P10/P90 are ensemble percentiles, not guaranteed real-world bounds.</p>
            <span class="probability-legend__missing">Hatched = unavailable</span>
          </div>
        `;
      }
      const units = selectedProbabilityVariable === "rainfall" ? "mm day⁻¹" : "°C";
      const ticks = selectedProbabilityVariable === "rainfall"
        ? ["0", "0.5", "2", "5", "10", "20", "≥30"]
        : ["0", "0.25", "1", "2.5", "5", "8", "≥10"];
      return `
        <div class="probability-legend">
          <strong>Ensemble spread: P90 − P10</strong>
          <div class="probability-legend__spread-gradient" aria-hidden="true"></div>
          <div class="probability-legend__spread-ticks">
            ${ticks.map((label) => `<span>${label}</span>`).join("")}
          </div>
          <p>Fixed, perceptually stretched ${units} scale across all weeks; tick labels remain physical values. Darker blue indicates a wider range across ensemble members.</p>
          <span class="probability-legend__missing">Hatched = unavailable</span>
        </div>
      `;
    }
    if (selectedProbabilityProduct === "category_margin") {
      return `
        <div class="probability-legend">
          <strong>Leading-category margin</strong>
          <div class="probability-legend__gradient is-margin"></div>
          <div class="probability-legend__ticks"><span>0 points</span><span>10</span><span>30</span><span>50</span><span>100</span></div>
          <p>Difference between the largest and second-largest tercile probabilities. Larger separation is not forecast confidence, calibration, accuracy, or skill.</p>
          <span class="probability-legend__missing">Hatched = unavailable</span>
        </div>
      `;
    }
    if (selectedProbabilityProduct !== "most_likely") {
      return `
        <div class="probability-legend">
          <strong>Raw ensemble probability</strong>
          <div class="probability-legend__gradient is-probability"></div>
          <div class="probability-legend__ticks"><span>0%</span><span>33%</span><span>67%</span><span>100%</span></div>
          <p>A standard tercile's climatological probability is approximately one-third where the reference supports three distinct categories.</p>
          <span class="probability-legend__missing">Hatched = unavailable</span>
        </div>
      `;
    }
    const below = selectedProbabilityVariable === "rainfall" ? "Drier" : "Cooler";
    const above = selectedProbabilityVariable === "rainfall" ? "Wetter" : "Warmer";
    return `
      <div class="probability-legend">
        <strong>Most likely tercile</strong>
        <div class="probability-legend__categories" data-variable="${selectedProbabilityVariable}">
          <span class="is-below">${below}</span>
          <span class="is-near">Near normal</span>
          <span class="is-above">${above}</span>
          <span class="is-tie">No unique leader</span>
        </div>
        <div class="probability-legend__intensity"><i></i><span>Weak preference</span><span>Stronger member fraction</span></div>
        <p>Hue identifies the leading category; deeper colour means more members support it. A leading category is not a skill or confidence score.</p>
        <span class="probability-legend__missing">Hatched = unavailable</span>
      </div>
    `;
  }

  function update(animateMaps: boolean): void {
    updateControls();
    rangeSelect.value = String(rangeStart);
    windModeControl
      .querySelectorAll<HTMLButtonElement>("button[data-wind-mode]")
      .forEach((button) => {
        const active = button.dataset.windMode === windRenderingMode;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });

    if (selectedView === "mean") {
      const product = PRESENTATION_PRODUCTS[selectedProduct];
      container.querySelector<HTMLElement>(".india-sheet")!.dataset.product =
      selectedProduct;
      container
        .querySelectorAll<HTMLButtonElement>(".india-product-tabs button")
        .forEach((button) => {
          const active = button.dataset.product === selectedProduct;
          button.classList.toggle("is-active", active);
          button.setAttribute("aria-pressed", String(active));
        });
      positionProductIndicator();
      container.querySelector(".india-selected-product")!.textContent = product.label;
      container.querySelector("#india-product-explanation")!.textContent =
        PLAIN_LANGUAGE_PRODUCT_DESCRIPTIONS[selectedProduct];
      makeMapPanels(
        activeForecast.weeks.slice(rangeStart, rangeStart + 4)
          .map((week) => displayWeek(week, selectedProduct)),
        (frame, week) => {
          const map = new ForecastMap(
            frame,
            activeForecast,
            activeGeography,
            isWindProduct(selectedProduct) ? undefined : handleLocationSelection,
            selectedLocation,
          );
          map.render(selectedProduct, week, product, windRenderingMode);
        },
      );
      const legend = container.querySelector<HTMLDivElement>("#india-shared-legend")!;
      legend.style.setProperty("--legend-under", product.legend.under);
      legend.style.setProperty("--legend-over", product.legend.over);
      legend.replaceChildren(createLegend(product));
      container.querySelector("#india-visual-note")!.textContent = isWindProduct(selectedProduct)
        ? `${product.description}. ${windRenderingMode === "streamlines" ? `Streamlines trace the interpolated ${selectedProduct === "wind850_anomaly" ? "anomaly " : ""}flow and include direction markers.` : "Arrows sample every third native grid point and use one product-specific scale across all weeks."} Shading is visually interpolated 1.5°→0.25°; hover values remain native-grid values.`
        : `${product.description.replace("100-member", `${activeForecast.issue.members}-member`)}. Visual-only bilinear interpolation from the ${activeForecast.grid.spacing_degrees}° native grid; hover values remain native-grid values.`;
      container.querySelector("#india-baseline-note")!.textContent = product.baseline
        ? "Anomaly is the forecast minus the model's typical value for the same season and forecast lead, estimated from 2002–2021 reforecasts."
        : activeDomain?.id !== "india"
          ? "Configured-domain v1 provides raw rainfall and temperature maps only; anomalies, probabilities, regional summaries, and verification are withheld."
          : sourceId === "ifs"
          ? "Main experimental IFS initialization using ECMWF Open Data; IFS skin temperature over ocean is the disclosed SST proxy."
          : sourceId === "gfs"
          ? "Secondary experimental initialization from operational analysis and short-range GFS proxy inputs."
          : "Delayed ERA5 reference initialization; not near-real-time operational guidance.";
      renderPanel();
    } else if (selectedView === "extremes") {
      const key = extremeProductKey();
      const supported = Boolean(
        activeForecast.extreme_definition &&
        availableExtremeProducts.includes(key) &&
        activeForecast.weeks[0]?.fields[key],
      );
      if (!supported) {
        panelGrid.innerHTML = `
          <div class="probability-unavailable-state" role="note">
            <strong>Extreme products are unavailable for this issue</strong>
            <p>No synthetic or substitute data are shown. Select IFS 26 September 2026 to inspect the first supported model-relative EFI/SOT package.</p>
          </div>
        `;
        container.querySelector(".india-selected-product")!.textContent =
          "Extreme products unavailable";
        container.querySelector("#india-product-explanation")!.textContent =
          "This issue does not carry a matching native model-climate extreme package.";
        container.querySelector<HTMLDivElement>("#india-shared-legend")!
          .replaceChildren();
        container.querySelector("#india-visual-note")!.textContent =
          "No synthetic or substitute EFI/SOT field is displayed.";
        container.querySelector("#india-baseline-note")!.textContent =
          "Extreme products are published only for explicitly supported issues.";
        panelHost.hidden = true;
        panelHost.replaceChildren();
      } else {
        const product = activeForecast.products[key]!;
        container.querySelector<HTMLElement>(".india-sheet")!.dataset.product = key;
        container.querySelector(".india-selected-product")!.textContent = product.label;
        container.querySelector("#india-product-explanation")!.textContent =
          product.description;
        makeMapPanels(
          activeForecast.weeks.slice(rangeStart, rangeStart + 4),
          (frame, week) => {
            const map = new ForecastMap(
              frame,
              activeForecast,
              activeGeography,
              handleLocationSelection,
              selectedLocation,
            );
            map.render(key, week, product);
          },
        );
        const legend = container.querySelector<HTMLDivElement>("#india-shared-legend")!;
        legend.style.setProperty("--legend-under", product.legend.under);
        legend.style.setProperty("--legend-over", product.legend.over);
        legend.replaceChildren(createLegend(product));
        container.querySelector("#india-visual-note")!.textContent =
          key.endsWith("efi")
            ? "Fixed −1 to +1 scale across all weeks; reference levels are marked at −0.8, −0.5, 0, +0.5, and +0.8. Hatched cells are unavailable, not zero."
            : "Fixed SOT bins across all weeks. Values above +2 are retained in the data and shown with the >2 legend bin; hatched cells are unavailable, not zero.";
        container.querySelector("#india-baseline-note")!.textContent =
          activeForecast.extreme_definition!.warning;
        renderPanel();
      }
    } else if (regionalOutlook) {
      const hasSummary = regionalOutlook.weeks.every(
        (week) => Boolean(week.summary_fields?.[selectedProbabilityVariable]),
      );
      const spreadButton = container.querySelector<HTMLButtonElement>(
        '[data-forecast-view="spread"]',
      )!;
      spreadButton.disabled = !hasSummary;
      spreadButton.title = hasSummary
        ? ""
        : "This archived issue predates grid quantile summaries.";
      if (selectedView === "spread" && !hasSummary) {
        panelGrid.innerHTML = `
          <div class="probability-unavailable-state" role="note">
            <strong>Ensemble spread unavailable for this issue</strong>
            <p>The published package contains real tercile probabilities but predates P10–P90 grid summaries. Nothing has been reconstructed from the mean.</p>
          </div>
        `;
      } else {
        const probabilisticWeeks = activeForecast.weeks.slice(
          rangeStart,
          rangeStart + 4,
        );
        makeMapPanels(probabilisticWeeks, (frame, forecastWeek) => {
          const week = regionalOutlook!.weeks.find(
            (candidate) => candidate.week === forecastWeek.week,
          );
          if (!week) return;
          const map = new ProbabilisticForecastMap(
            frame,
            activeForecast,
            regionalOutlook!,
            activeGeography,
            handleLocationSelection,
          );
          map.render({
            variable: selectedProbabilityVariable,
            week,
            product: selectedView === "spread"
              ? selectedDistributionProduct
              : selectedProbabilityProduct,
            extent: selectedProbabilityExtent,
            selected: selectedLocation,
          });
        });
      }
      const productTitle = selectedView === "spread"
        ? selectedDistributionProduct === "spread"
          ? "Ensemble spread: P90 − P10"
          : selectedDistributionProduct === "p10"
            ? "P10 lower ensemble outcome"
            : selectedDistributionProduct === "p50"
              ? "Median ensemble outcome"
              : "P90 upper ensemble outcome"
        : selectedProbabilityProduct === "most_likely"
          ? "Most likely tercile"
          : selectedProbabilityProduct === "category_margin"
            ? "Leading-category probability margin"
          : `${selectedProbabilityProduct.replaceAll("_", " ")} probability`;
      container.querySelector(".india-selected-product")!.textContent = productTitle;
      container.querySelector("#india-product-explanation")!.textContent =
        selectedView === "spread"
          ? selectedDistributionProduct === "spread"
            ? "Shows the width of the central 80% ensemble interval in the forecast quantity's physical units."
            : "Shows a selected ensemble percentile in the forecast quantity's physical units."
          : selectedProbabilityProduct === "category_margin"
            ? "Shows the percentage-point separation between the leading and second-place tercile categories."
            : "Shows raw ensemble fractions relative to lead-matched lower and upper model-climatology tercile thresholds.";
      container.querySelector("#india-visual-note")!.textContent =
        selectedProbabilityExtent === "regional"
          ? selectedView === "spread"
            ? selectedDistributionProduct === "spread"
              ? "Regional grid shows every available forecast cell from about 60–99°E and 0–39°N. It reaches western Thailand and Sumatra, but not all of Thailand or Indonesia. Low spread does not establish that the forecast is correct."
              : "Regional grid shows the selected member-derived percentile across every available cell from about 60–99°E and 0–39°N. Visual interpolation affects presentation only."
            : "Regional grid uses complete lead-matched model-climatology thresholds across all available cells from about 60–99°E and 0–39°N. Visual interpolation affects presentation only."
          : selectedView === "spread"
            ? selectedDistributionProduct === "spread"
              ? "Low spread does not establish that the forecast is correct. Scales are fixed across all forecast weeks."
              : "P10 and P90 are ensemble percentiles, not confidence bounds or guarantees. Scales are fixed across all forecast weeks."
            : "Visual interpolation affects presentation only; tooltips report native-grid probabilities and actual valid-member counts.";
      container.querySelector<HTMLDivElement>("#india-shared-legend")!.innerHTML =
        probabilityLegend();
      container.querySelector("#india-baseline-note")!.textContent =
        "Probabilities are fractions of available members, not necessarily calibrated event frequencies. The reference is the existing lead-matched 2002–2021 native model climatology.";
      renderPanel();
    }

    if (animateMaps) {
      if (panelAnimationTimer !== undefined) window.clearTimeout(panelAnimationTimer);
      panelGrid.classList.remove("is-refreshing");
      void panelGrid.offsetWidth;
      panelGrid.classList.add("is-refreshing");
      panelAnimationTimer = window.setTimeout(() => {
        panelGrid.classList.remove("is-refreshing");
        panelAnimationTimer = undefined;
      }, 380);
    }
  }

  update(false);
  if (initializationComparison && data.comparisonForecasts) {
    renderInitializationComparison(
      container,
      initializationComparison,
      data.comparisonForecasts,
      activeGeography,
    );
  }
  return () => {
    requestGeneration += 1;
    requestController.abort();
    if (panelAnimationTimer !== undefined) window.clearTimeout(panelAnimationTimer);
    if (productIndicatorFrame !== undefined) {
      window.cancelAnimationFrame(productIndicatorFrame);
    }
    window.removeEventListener("resize", positionProductIndicator);
  };
}
