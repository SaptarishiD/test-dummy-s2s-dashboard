import type {
  ForecastData,
  ForecastGridSelection,
  ForecastWeek,
  ProbabilisticVariable,
  ProductKey,
} from "../types";

function friendlyDate(value: string, includeYear = false): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    ...(includeYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}

function display(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(2)
    : "Unavailable";
}

function valueAt(
  week: ForecastWeek,
  key: ProductKey,
  index: number,
): number | null | undefined {
  return week.fields[key]?.[index];
}

function cdfChart(
  week: ForecastWeek,
  variable: ProbabilisticVariable,
  index: number,
): string {
  const summary = week.distribution_summaries?.[variable];
  if (!summary) {
    return '<p class="extreme-panel__unavailable">CDF summaries are unavailable.</p>';
  }
  const forecast = summary.forecast.map((row) => row[index]);
  const climate = summary.climate.map((row) => row[index]);
  const finite = [...forecast, ...climate].filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!finite.length) {
    return '<p class="extreme-panel__unavailable">CDF summaries are unavailable at this cell.</p>';
  }
  const minimum = Math.min(...finite);
  const maximum = Math.max(...finite);
  const span = maximum - minimum || 1;
  const points = (values: Array<number | null>): string => values
    .map((value, pointIndex) => {
      if (value === null || !Number.isFinite(value)) return "";
      const x = 42 + ((value - minimum) / span) * 340;
      const y = 152 - summary.probabilities[pointIndex] * 124;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
  return `
    <svg class="extreme-cdf-chart" viewBox="0 0 420 180" role="img" aria-label="Forecast and model-climate cumulative distribution percentile summaries">
      <line x1="42" y1="152" x2="382" y2="152"></line>
      <line x1="42" y1="28" x2="42" y2="152"></line>
      <polyline class="is-climate" points="${points(climate)}"></polyline>
      <polyline class="is-forecast" points="${points(forecast)}"></polyline>
      <text x="42" y="172">${minimum.toFixed(1)}</text>
      <text x="382" y="172" text-anchor="end">${maximum.toFixed(1)}</text>
      <text x="50" y="21">Compact percentile summaries</text>
    </svg>
    <div class="extreme-cdf-key" aria-hidden="true"><span class="is-forecast">Forecast</span><span class="is-climate">Model climate</span></div>
  `;
}

export function renderExtremeForecastPanel(
  host: HTMLElement,
  forecast: ForecastData,
  variable: ProbabilisticVariable,
  selection: ForecastGridSelection,
  onWeek: (week: number) => void,
  onClose: () => void,
): void {
  const definition = forecast.extreme_definition;
  if (!definition) {
    host.innerHTML = "";
    host.hidden = true;
    return;
  }
  const index = selection.latitude_index * forecast.grid.longitude.length +
    selection.longitude_index;
  const week = forecast.weeks.find((candidate) => candidate.week === selection.week) ??
    forecast.weeks[0];
  const efiKey = `${variable}_efi` as ProductKey;
  const upperKey = `${variable}_sot_upper` as ProductKey;
  const efi = valueAt(week, efiKey, index);
  const numericEfi = typeof efi === "number" && Number.isFinite(efi) ? efi : null;
  const direction = variable === "rainfall"
    ? numericEfi !== null && numericEfi >= 0 ? "wetter" : "drier"
    : numericEfi !== null && numericEfi >= 0 ? "warmer" : "cooler";
  const interpretation = numericEfi === null
    ? "cannot be interpreted because the index is unavailable"
    : Math.abs(numericEfi) >= 0.8
      ? `is shifted very unusually toward ${direction} outcomes relative to its model climate`
      : Math.abs(numericEfi) >= 0.5
        ? `is shifted unusually toward ${direction} outcomes relative to its model climate`
        : `does not show a strong shift toward ${direction} outcomes relative to its model climate`;

  host.hidden = false;
  host.innerHTML = `
    <aside class="extreme-location-panel" aria-labelledby="extreme-panel-title">
      <header>
        <div>
          <span>Selected native grid cell</span>
          <h2 id="extreme-panel-title" tabindex="-1">${selection.latitude.toFixed(1)}°N · ${selection.longitude.toFixed(1)}°E</h2>
          <p>Week ${week.week} · ${friendlyDate(week.valid_start)}–${friendlyDate(week.valid_end, true)}</p>
        </div>
        <div class="extreme-panel__actions">
          <button type="button" class="extreme-panel__close" aria-label="Close location details">×</button>
        </div>
      </header>
      <p class="extreme-panel__support-note">Values describe this ${forecast.grid.spacing_degrees}° model grid cell, not a district or regional average.</p>
      <div class="extreme-panel__layout">
        <section class="extreme-panel__summary">
          <h3>Selected week</h3>
          <dl>
            <div><dt>EFI</dt><dd>${display(efi)}</dd></div>
          </dl>
          <p>The raw ensemble ${interpretation}. EFI compares the full distribution; SOT describes displacement of the applicable tail.</p>
        </section>
        <section>
          <h3>Week 1–6 timeline · no smoothing</h3>
          <div class="extreme-timeline">
            ${forecast.weeks.map((candidate) => `
              <button type="button" data-extreme-week="${candidate.week}" class="${candidate.week === week.week ? "is-active" : ""}" aria-pressed="${candidate.week === week.week}">
                <span>W${candidate.week}</span>
                <strong>EFI ${display(valueAt(candidate, efiKey, index))}</strong>
                <small>${friendlyDate(candidate.valid_start)}–${friendlyDate(candidate.valid_end)}</small>
              </button>
            `).join("")}
          </div>
        </section>
      </div>
      <p class="extreme-panel__accuracy-note">EFI and SOT describe how unusual the raw ensemble is relative to its model climate; they do not establish forecast accuracy or guaranteed impacts.</p>
      <details class="extreme-panel__advanced">
        <summary>Advanced distribution details</summary>
        <div class="extreme-panel__advanced-grid">
          <section class="extreme-panel__summary">
            <h3>Shift of Tails · selected week</h3>
            <dl>
              <div><dt>Upper-tail SOT</dt><dd>${display(valueAt(week, upperKey, index))}</dd></div>
              ${variable === "temperature" ? `<div><dt>Lower-tail SOT</dt><dd>${display(valueAt(week, "temperature_sot_lower", index))}</dd></div>` : ""}
            </dl>
          </section>
          <section>
            <h3>Forecast versus model climate</h3>
            ${cdfChart(week, variable, index)}
          </section>
        </div>
        <footer>
          <strong>${week.extreme_samples?.forecast_valid_member_count[index] ?? "—"} forecast members · ${week.extreme_samples?.climate_valid_sample_count[index] ?? "—"} climate samples</strong>
          <span>${definition.reference_id}</span>
          <p>${definition.warning}</p>
        </footer>
      </details>
    </aside>
  `;
  host.querySelector<HTMLButtonElement>(".extreme-panel__close")
    ?.addEventListener("click", onClose);
  host.querySelectorAll<HTMLButtonElement>("[data-extreme-week]")
    .forEach((button) => button.addEventListener("click", () => {
      onWeek(Number(button.dataset.extremeWeek));
    }));
  host.querySelector<HTMLElement>("#extreme-panel-title")
    ?.focus({ preventScroll: true });
}
