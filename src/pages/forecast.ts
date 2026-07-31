import { ForecastMap } from "../components/ForecastMap";
import { createLegend } from "../components/Legend";
import type {
  AppData,
  ForecastWeek,
  ProductDefinition,
  ProductKey,
} from "../types";

const PRODUCT_ORDER: ProductKey[] = [
  "rainfall_total",
  "rainfall_anomaly",
  "temperature_mean",
  "temperature_anomaly",
];

const PRESENTATION_PRODUCTS: Record<ProductKey, ProductDefinition> = {
  rainfall_total: {
    label: "Weekly-mean rainfall rate",
    short_label: "Rainfall rate",
    description: "Weekly mean of the daily 100-member ensemble-mean rainfall forecast",
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
    label: "Weekly-mean rainfall anomaly",
    short_label: "Rainfall anomaly",
    description: "Forecast minus calendar-interpolated, lead-matched 2002–2021 model climatology",
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
    label: "Weekly-mean 2 m temperature",
    short_label: "Temperature",
    description: "Weekly mean of the daily 100-member ensemble-mean 2-metre temperature",
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
    label: "Weekly-mean temperature anomaly",
    short_label: "Temperature anomaly",
    description: "Forecast minus calendar-interpolated, lead-matched 2002–2021 model climatology",
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
};

function friendlyDate(isoDate: string, includeYear = false): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    ...(includeYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(new Date(`${isoDate}T12:00:00Z`));
}

function displayWeek(week: ForecastWeek, product: ProductKey): ForecastWeek {
  if (product !== "rainfall_total") return week;
  return {
    ...week,
    fields: {
      ...week.fields,
      rainfall_total: week.fields.rainfall_total.map((value) => value / 7),
    },
  };
}

export function renderForecastPage(container: HTMLElement, data: AppData): void {
  const { forecast, validation } = data;
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

  container.innerHTML = `
    <section class="india-sheet">
      <header class="india-sheet__header">
        <div>
          <span class="india-sheet__brand">Atmosphere 42 · India outlook</span>
          <h1 id="india-product-title">Weekly-mean rainfall anomaly</h1>
          <p>28 July 2026 forecast start <i>•</i> 26–27 July daily-mean inputs <i>•</i> ${forecast.issue.members}-member ensemble mean <i>•</i> Weeks 1–6</p>
        </div>
        <span class="india-experimental">Experimental</span>
      </header>

      <div class="india-toolbar">
        <div class="india-product-tabs" id="india-product-tabs" aria-label="India forecast field"></div>
        <div class="india-range-tabs" aria-label="Displayed forecast weeks">
          <button type="button" data-range="0" class="is-active">Weeks 1–4</button>
          <button type="button" data-range="2">Weeks 3–6</button>
        </div>
      </div>

      <div class="india-panel-grid" id="india-panel-grid"></div>
      <div class="india-shared-legend" id="india-shared-legend"></div>
      <p class="india-visual-note" id="india-visual-note"></p>

      <footer class="india-sheet__footer">
        <p id="india-baseline-note"></p>
        <span>Research guidance · Not an operational warning</span>
      </footer>
    </section>
  `;

  let selectedProduct: ProductKey = "rainfall_anomaly";
  let rangeStart = 0;
  const productTabs = container.querySelector<HTMLDivElement>("#india-product-tabs")!;
  const panelGrid = container.querySelector<HTMLDivElement>("#india-panel-grid")!;

  PRODUCT_ORDER.forEach((productKey) => {
    const product = PRESENTATION_PRODUCTS[productKey];
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.product = productKey;
    button.innerHTML = `<span class="product-swatch product-swatch--${productKey}" aria-hidden="true"></span><strong>${product.short_label}</strong>`;
    button.addEventListener("click", () => {
      selectedProduct = productKey;
      update();
    });
    productTabs.append(button);
  });

  container
    .querySelectorAll<HTMLButtonElement>(".india-range-tabs button")
    .forEach((button) => {
      button.addEventListener("click", () => {
        rangeStart = Number(button.dataset.range);
        update();
      });
    });

  function update(): void {
    const product = PRESENTATION_PRODUCTS[selectedProduct];
    container
      .querySelectorAll<HTMLButtonElement>(".india-product-tabs button")
      .forEach((button) => {
        const active = button.dataset.product === selectedProduct;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });
    container
      .querySelectorAll<HTMLButtonElement>(".india-range-tabs button")
      .forEach((button) => {
        const active = Number(button.dataset.range) === rangeStart;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
      });

    container.querySelector("#india-product-title")!.textContent = product.label;
    panelGrid.replaceChildren();
    forecast.weeks.slice(rangeStart, rangeStart + 4).forEach((sourceWeek) => {
      const week = displayWeek(sourceWeek, selectedProduct);
      const panel = document.createElement("article");
      panel.className = "india-map-panel";
      panel.innerHTML = `
        <h2><strong>Week ${week.week}</strong><i>|</i>${friendlyDate(week.valid_start)} – ${friendlyDate(week.valid_end, true)}</h2>
        <div class="india-map-frame"></div>
      `;
      panelGrid.append(panel);
      const frame = panel.querySelector<HTMLDivElement>(".india-map-frame")!;
      const map = new ForecastMap(
        frame,
        forecast,
        data.outline,
        data.world,
        data.indiaAdmin,
      );
      map.render(selectedProduct, week, product);
    });

    const legend = container.querySelector<HTMLDivElement>("#india-shared-legend")!;
    legend.style.setProperty("--legend-under", product.legend.under);
    legend.style.setProperty("--legend-over", product.legend.over);
    legend.replaceChildren(createLegend(product));
    container.querySelector("#india-visual-note")!.textContent =
      `${product.description}. Visual-only bilinear interpolation 1.5°→0.25°; hover values remain native-grid values.`;
    container.querySelector("#india-baseline-note")!.textContent = product.baseline
      ? "Anomaly uses calendar- and lead-matched 2002–2021 native-reforecast climatology (0725/0728 interpolation)."
      : "Experimental initialization from operational analysis and short-range forecast proxy inputs.";
  }

  update();
}
