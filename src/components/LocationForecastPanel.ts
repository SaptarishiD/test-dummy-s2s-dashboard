import type {
  ForecastGridSelection,
  ProbabilisticVariable,
  RegionalOutlookData,
  TercileCategory,
} from "../types";

const CATEGORY_LABELS: Record<
  ProbabilisticVariable,
  Record<TercileCategory, string>
> = {
  rainfall: {
    below_normal: "Drier",
    near_normal: "Near normal",
    above_normal: "Wetter",
  },
  temperature: {
    below_normal: "Cooler",
    near_normal: "Near normal",
    above_normal: "Warmer",
  },
};

function friendlyDate(value: string, includeYear = false): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    ...(includeYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}

function valueText(value: number | null | undefined, units: string): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "Unavailable"
    : `${value.toFixed(2)} ${units}`;
}

function probabilityText(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : `${value.toFixed(value % 1 === 0 ? 0 : 1)}%`;
}

function probabilityWidth(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "0";
  }
  return Math.max(0, Math.min(100, value)).toFixed(2);
}

function finiteValue(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function selectedWeekRangeStrip(
  values: Array<number | null | undefined>,
  units: string,
): string {
  const [p10, p25, p50, p75, p90] = values;
  const available = values.every(finiteValue);
  const ordered = available &&
    (p10 as number) <= (p25 as number) &&
    (p25 as number) <= (p50 as number) &&
    (p50 as number) <= (p75 as number) &&
    (p75 as number) <= (p90 as number);

  if (!ordered) {
    return `
      <div class="probability-range-strip probability-range-strip--unavailable" role="note">
        <strong>Selected-week range unavailable</strong>
        <span>The five required ordered quantiles are not available at this cell.</span>
      </div>
    `;
  }

  const lower = p10 as number;
  const upper = p90 as number;
  const span = upper - lower;
  const position = (value: number): number =>
    span === 0 ? 50 : Math.max(0, Math.min(100, (value - lower) / span * 100));
  const p25Position = position(p25 as number);
  const p50Position = position(p50 as number);
  const p75Position = position(p75 as number);
  const degenerate = span === 0;
  const ariaLabel = degenerate
    ? `All selected-week quantiles equal ${valueText(lower, units)}`
    : `Selected-week ensemble range: P10 ${valueText(lower, units)}, P25 ${valueText(p25, units)}, median ${valueText(p50, units)}, P75 ${valueText(p75, units)}, P90 ${valueText(upper, units)}`;

  return `
    <div class="probability-range-strip${degenerate ? " is-degenerate" : ""}">
      <div class="probability-range-strip__heading">
        <strong>P10–P90 range</strong>
        <span>${degenerate ? "All quantiles equal" : "Central 80% of members"}</span>
      </div>
      <div class="probability-range-strip__graphic" role="img" aria-label="${ariaLabel}">
        <div class="probability-range-strip__track" aria-hidden="true">
          <i class="probability-range-strip__whisker probability-range-strip__whisker--low" style="left:0%"></i>
          <i class="probability-range-strip__outer" style="left:0%;width:100%"></i>
          <i class="probability-range-strip__inner" style="left:${p25Position.toFixed(2)}%;width:${Math.max(0, p75Position - p25Position).toFixed(2)}%"></i>
          <i class="probability-range-strip__median" style="left:${p50Position.toFixed(2)}%"></i>
          <i class="probability-range-strip__whisker probability-range-strip__whisker--high" style="left:100%"></i>
        </div>
      </div>
      <div class="probability-range-strip__values">
        <span><small>P10</small><strong>${valueText(lower, units)}</strong></span>
        <span><small>P25</small><strong>${valueText(p25, units)}</strong></span>
        <span><small>Median</small><strong>${valueText(p50, units)}</strong></span>
        <span><small>P75</small><strong>${valueText(p75, units)}</strong></span>
        <span><small>P90</small><strong>${valueText(upper, units)}</strong></span>
      </div>
    </div>
  `;
}

function forecastFingerprint(
  outlook: RegionalOutlookData,
  variable: ProbabilisticVariable,
  index: number,
  selectedWeek: number,
  fallbackUnits: string,
): string {
  const labels = CATEGORY_LABELS[variable];
  const categories: TercileCategory[] = [
    "below_normal",
    "near_normal",
    "above_normal",
  ];
  const expected = outlook.issue.expected_members ?? outlook.issue.members;

  return `
    <div class="probability-fingerprint" role="list" aria-label="Six-week probabilistic forecast fingerprint">
      ${outlook.weeks.map((forecastWeek) => {
        const fields = forecastWeek.probability_fields?.[variable];
        const categoryProbabilities = categories.map((category) => ({
          category,
          probability: fields?.[category]?.[index] ?? null,
        }));
        const probabilitiesAvailable = categoryProbabilities.every(({ probability }) =>
          finiteValue(probability)
        );
        const maximum = probabilitiesAvailable
          ? Math.max(...categoryProbabilities.map(({ probability }) => probability as number))
          : null;
        const leaders = maximum === null
          ? []
          : categoryProbabilities.filter(({ probability }) => probability === maximum);
        const leader = leaders.length === 1 ? leaders[0] : null;
        const summary = forecastWeek.summary_fields?.[variable];
        const p10 = summary?.p10[index] ?? null;
        const p90 = summary?.p90[index] ?? null;
        const spread = finiteValue(p10) && finiteValue(p90) && p90 >= p10
          ? p90 - p10
          : null;
        const valid = summary?.valid_member_count[index] ?? null;
        const units = summary?.units ?? fallbackUnits;
        const available = probabilitiesAvailable || spread !== null;
        const stateClass = leader
          ? ` is-${leader.category.replace("_normal", "")}`
          : leaders.length > 1
            ? " is-tie"
            : " is-unavailable";
        const categoryText = leader
          ? labels[leader.category]
          : leaders.length > 1
            ? "No unique leader"
            : "Terciles unavailable";
        const leadingSupportCount = maximum !== null && finiteValue(valid)
          ? Math.round(maximum / 100 * valid)
          : null;
        const supportText = leader
          ? `${probabilityText(leader.probability)} · ${leadingSupportCount === null ? "member count unavailable" : `${leadingSupportCount}/${valid} members`}`
          : leaders.length > 1 && maximum !== null
            ? `Tied at ${probabilityText(maximum)}${leadingSupportCount === null ? "" : ` · ${leadingSupportCount}/${valid} members each`}`
            : "Support unavailable";
        const memberText = finiteValue(valid)
          ? `${valid}/${expected} members available`
          : "Member count unavailable";
        const spreadText = spread === null ? "Spread unavailable" : `P90−P10 ${valueText(spread, units)}`;
        const selected = forecastWeek.week === selectedWeek;
        const ariaLabel = `Week ${forecastWeek.week}, ${friendlyDate(forecastWeek.valid_start)} to ${friendlyDate(forecastWeek.valid_end)}: ${categoryText}, ${supportText}, ${spreadText}, ${memberText}`;

        return `
          <article
            class="probability-fingerprint__tile${stateClass}${selected ? " is-selected" : ""}${available ? "" : " is-empty"}"
            role="listitem"
            aria-label="${ariaLabel}"
            ${selected ? 'aria-current="true"' : ""}
          >
            <div class="probability-fingerprint__week">
              <strong>W${forecastWeek.week}</strong>
              <span>${friendlyDate(forecastWeek.valid_start)}–${friendlyDate(forecastWeek.valid_end)}</span>
            </div>
            <div class="probability-fingerprint__outcome">
              <i aria-hidden="true"></i>
              <strong>${categoryText}</strong>
              <span>${supportText}</span>
            </div>
            <p class="probability-fingerprint__spread">${spreadText}</p>
            <small class="probability-fingerprint__members">${memberText}</small>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function weeklyTercileEvolution(
  outlook: RegionalOutlookData,
  variable: ProbabilisticVariable,
  index: number,
  selectedWeek: number,
): string {
  const labels = CATEGORY_LABELS[variable];
  const weeklyProbabilities = outlook.weeks.map((week) => {
    const fields = week.probability_fields?.[variable];
    const below = fields?.below_normal[index] ?? null;
    const near = fields?.near_normal[index] ?? null;
    const above = fields?.above_normal[index] ?? null;
    const available = [below, near, above].every(
      (value) => typeof value === "number" && Number.isFinite(value),
    );
    return { week, below, near, above, available };
  });

  if (!weeklyProbabilities.some(({ available }) => available)) {
    return `
      <div class="probability-panel__unavailable" role="note">
        <strong>Forecast-week probabilities unavailable at this cell</strong>
        <p>No forecast week meets the member-completeness and reference-climatology requirements here.</p>
      </div>
    `;
  }

  return `
    <div class="probability-weekly-terciles" role="list" aria-label="Raw ensemble tercile probabilities by forecast week">
      ${weeklyProbabilities.map(({ week, below, near, above, available }) => `
        <article
          class="probability-weekly-terciles__week${week.week === selectedWeek ? " is-selected" : ""}"
          role="listitem"
          ${week.week === selectedWeek ? 'aria-current="true"' : ""}
        >
          <div class="probability-weekly-terciles__heading">
            <strong>Week ${week.week}</strong>
            <span>${friendlyDate(week.valid_start)}–${friendlyDate(week.valid_end)}</span>
          </div>
          ${available ? `
            <div
              class="probability-stacked-bar probability-weekly-terciles__bar"
              role="img"
              aria-label="Week ${week.week}, ${friendlyDate(week.valid_start)} to ${friendlyDate(week.valid_end)}: ${labels.below_normal} ${probabilityText(below)}, ${labels.near_normal} ${probabilityText(near)}, ${labels.above_normal} ${probabilityText(above)}"
            >
              <i class="is-below" style="width:${probabilityWidth(below)}%"></i>
              <i class="is-near" style="width:${probabilityWidth(near)}%"></i>
              <i class="is-above" style="width:${probabilityWidth(above)}%"></i>
            </div>
            <p class="probability-weekly-terciles__values">
              <span>${labels.below_normal} <strong>${probabilityText(below)}</strong></span>
              <span>${labels.near_normal} <strong>${probabilityText(near)}</strong></span>
              <span>${labels.above_normal} <strong>${probabilityText(above)}</strong></span>
            </p>
          ` : `
            <p class="probability-weekly-terciles__unavailable" role="note">Probabilities unavailable for this week at the selected cell.</p>
          `}
        </article>
      `).join("")}
    </div>
  `;
}

function distributionChart(
  outlook: RegionalOutlookData,
  variable: ProbabilisticVariable,
  index: number,
): string {
  const summaries = outlook.weeks.map((week) => week.summary_fields?.[variable]);
  if (summaries.some((summary) => !summary)) {
    return `
      <div class="probability-panel__unavailable" role="note">
        <strong>Weekly distribution chart unavailable</strong>
        <p>This archived issue contains tercile probabilities but predates grid quantile summaries.</p>
      </div>
    `;
  }
  const available = summaries.every((summary) =>
    [
      summary?.p10[index],
      summary?.p25[index],
      summary?.p50[index],
      summary?.p75[index],
      summary?.p90[index],
    ].every((value) => typeof value === "number" && Number.isFinite(value))
  );
  if (!available) {
    return `
      <div class="probability-panel__unavailable" role="note">
        <strong>Weekly distribution chart unavailable at this cell</strong>
        <p>The configured member-completeness requirement was not met.</p>
      </div>
    `;
  }

  const width = 340;
  const height = 176;
  const left = 34;
  const right = 12;
  const top = 12;
  const bottom = 34;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const p10 = summaries.map((summary) => summary!.p10[index] as number);
  const p25 = summaries.map((summary) => summary!.p25[index] as number);
  const p50 = summaries.map((summary) => summary!.p50[index] as number);
  const p75 = summaries.map((summary) => summary!.p75[index] as number);
  const p90 = summaries.map((summary) => summary!.p90[index] as number);
  const climatology = summaries.map(
    (summary) => summary!.climatology_median[index],
  );
  const finiteReference = climatology.every(
    (value) => typeof value === "number" && Number.isFinite(value),
  );
  const values = [...p10, ...p90, ...(finiteReference ? climatology as number[] : [])];
  let minimum = Math.min(...values);
  let maximum = Math.max(...values);
  if (variable === "rainfall") minimum = Math.min(0, minimum);
  if (maximum <= minimum) maximum = minimum + 1;
  const padding = (maximum - minimum) * 0.08;
  minimum -= padding;
  maximum += padding;

  const x = (weekIndex: number): number =>
    left + weekIndex * chartWidth / Math.max(1, outlook.weeks.length - 1);
  const y = (value: number): number =>
    top + (maximum - value) / (maximum - minimum) * chartHeight;
  const points = (series: number[]): string =>
    series.map((value, weekIndex) => `${x(weekIndex)},${y(value)}`).join(" ");
  const band = (upper: number[], lower: number[]): string =>
    [
      ...upper.map((value, weekIndex) => `${x(weekIndex)},${y(value)}`),
      ...lower.map((value, weekIndex) =>
        `${x(weekIndex)},${y(value)}`
      ).reverse(),
    ].join(" ");

  return `
    <svg class="probability-distribution-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Forecast-week median with inner 50 percent and central 80 percent ensemble intervals">
      <line class="probability-chart__axis" x1="${left}" x2="${width - right}" y1="${top + chartHeight}" y2="${top + chartHeight}" />
      <polygon class="probability-chart__outer" points="${band(p90, p10)}" />
      <polygon class="probability-chart__inner" points="${band(p75, p25)}" />
      ${finiteReference ? `<polyline class="probability-chart__reference" points="${points(climatology as number[])}" />` : ""}
      <polyline class="probability-chart__median" points="${points(p50)}" />
      ${p50.map((value, weekIndex) => `
        <circle class="probability-chart__point" cx="${x(weekIndex)}" cy="${y(value)}" r="3">
          <title>Week ${weekIndex + 1}: median ${value.toFixed(2)}</title>
        </circle>
        <text class="probability-chart__week" x="${x(weekIndex)}" y="${height - 10}" text-anchor="middle">W${weekIndex + 1}</text>
      `).join("")}
      <text class="probability-chart__scale" x="${left - 6}" y="${top + 5}" text-anchor="end">${maximum.toFixed(1)}</text>
      <text class="probability-chart__scale" x="${left - 6}" y="${top + chartHeight}" text-anchor="end">${minimum.toFixed(1)}</text>
    </svg>
    <div class="probability-chart__key" aria-hidden="true">
      <span class="is-median">Median</span>
      <span class="is-inner">P25–P75</span>
      <span class="is-outer">P10–P90</span>
      ${finiteReference ? '<span class="is-reference">Model-climatology median</span>' : ""}
    </div>
    <ol class="probability-chart__periods" aria-label="Forecast-week valid dates">
      ${outlook.weeks.map((week) => `<li><strong>W${week.week}</strong><span>${friendlyDate(week.valid_start)}–${friendlyDate(week.valid_end)}</span></li>`).join("")}
    </ol>
  `;
}

export function renderLocationForecastPanel(
  host: HTMLElement,
  outlook: RegionalOutlookData,
  variable: ProbabilisticVariable,
  selection: ForecastGridSelection,
  onClose: () => void,
): void {
  const week = outlook.weeks.find((candidate) => candidate.week === selection.week) ??
    outlook.weeks[0];
  const index = selection.latitude_index * outlook.grid.longitude.length +
    selection.longitude_index;
  const summary = week.summary_fields?.[variable];
  const probabilities = week.probability_fields[variable];
  const below = probabilities.below_normal[index] ?? null;
  const near = probabilities.near_normal[index] ?? null;
  const above = probabilities.above_normal[index] ?? null;
  const probabilityAvailable = [below, near, above].every(
    (value) => typeof value === "number" && Number.isFinite(value),
  );
  const expected = outlook.issue.expected_members ?? outlook.issue.members;
  const valid = summary?.valid_member_count[index] ?? expected;
  const units = summary?.units ?? (variable === "rainfall" ? "mm day⁻¹" : "°C");
  const variableLabel = variable === "rainfall"
    ? "Weekly mean rainfall"
    : "Weekly mean 2 m temperature";
  const reference = outlook.probability_definition.reference_id ??
    "Lead-matched 2002–2021 native model climatology";

  host.innerHTML = `
    <aside class="probability-location-panel" data-variable="${variable}" aria-labelledby="probability-panel-title">
      <header class="probability-location-panel__header">
        <div>
          <span>Selected native grid cell</span>
          <h2 id="probability-panel-title" tabindex="-1">${selection.latitude.toFixed(1)}°N · ${selection.longitude.toFixed(1)}°E</h2>
          <p>${variableLabel} · Week ${week.week}<br>${friendlyDate(week.valid_start)}–${friendlyDate(week.valid_end, true)}</p>
        </div>
        <button type="button" class="probability-panel__close" aria-label="Close location details">×</button>
      </header>

      <p class="probability-panel__support-note">Values represent the selected ${outlook.grid.spacing_degrees}° model grid cell, not a district or regional average.</p>

      <section class="probability-panel__section" aria-labelledby="probability-summary-title">
        <h3 id="probability-summary-title">Forecast summary</h3>
        ${summary ? `
          <dl class="probability-summary-grid">
            <div><dt>Ensemble mean</dt><dd>${valueText(summary.mean[index], units)}</dd></div>
            <div><dt>Median</dt><dd>${valueText(summary.p50[index], units)}</dd></div>
            <div><dt>80% ensemble interval</dt><dd>${valueText(summary.p10[index], units)}–${valueText(summary.p90[index], units)}</dd></div>
            <div><dt>Valid members</dt><dd>${valid}/${expected}</dd></div>
          </dl>
          ${selectedWeekRangeStrip([
            summary.p10[index],
            summary.p25[index],
            summary.p50[index],
            summary.p75[index],
            summary.p90[index],
          ], units)}
        ` : `
          <div class="probability-panel__unavailable" role="note">
            <strong>Amount and quantile summary unavailable</strong>
            <p>This archived issue predates grid quantile summaries. Its published probabilities remain available below.</p>
          </div>
        `}
      </section>

      <section class="probability-panel__section" aria-labelledby="probability-tercile-title">
        <div class="probability-panel__section-heading">
          <h3 id="probability-tercile-title">Tercile probabilities</h3>
          <span>Raw ensemble probability</span>
        </div>
        ${probabilityAvailable ? `
          <div class="probability-stacked-bar" aria-label="Below ${probabilityText(below)}, near ${probabilityText(near)}, above ${probabilityText(above)}">
            <i class="is-below" style="width:${below}%"></i>
            <i class="is-near" style="width:${near}%"></i>
            <i class="is-above" style="width:${above}%"></i>
          </div>
          <div class="probability-stacked-values">
            <span><i class="is-below"></i><strong>${CATEGORY_LABELS[variable].below_normal}</strong><b>${probabilityText(below)}</b></span>
            <span><i class="is-near"></i><strong>${CATEGORY_LABELS[variable].near_normal}</strong><b>${probabilityText(near)}</b></span>
            <span><i class="is-above"></i><strong>${CATEGORY_LABELS[variable].above_normal}</strong><b>${probabilityText(above)}</b></span>
          </div>
          <p class="probability-panel__method">${valid}/${expected} available members · ${reference}. A standard tercile has a climatological probability near one-third where the reference distribution supports three distinct categories.</p>
        ` : `
          <div class="probability-panel__unavailable" role="note">
            <strong>Tercile probabilities unavailable at this cell</strong>
            <p>The member-completeness requirement was not met, or the reference climatology has repeated thresholds that do not define three distinct categories.</p>
          </div>
        `}
      </section>

      <section class="probability-panel__section" aria-labelledby="probability-fingerprint-title">
        <div class="probability-panel__section-heading">
          <h3 id="probability-fingerprint-title">Six-week forecast fingerprint</h3>
          <span>Outcome · support · spread</span>
        </div>
        <p class="probability-panel__section-copy">Each tile combines the leading tercile with its raw member support and the central 80% ensemble range. A tie is shown explicitly.</p>
        ${forecastFingerprint(outlook, variable, index, week.week, units)}
      </section>

      <section class="probability-panel__section" aria-labelledby="probability-chart-title">
        <h3 id="probability-chart-title">Distribution across forecast weeks</h3>
        <p class="probability-panel__section-copy">Points are weekly medians. Shaded bands are computed from members independently for each week; they are not smoothed or forced to widen.</p>
        ${distributionChart(outlook, variable, index)}
      </section>

      <section class="probability-panel__section" aria-labelledby="probability-weekly-terciles-title">
        <div class="probability-panel__section-heading">
          <h3 id="probability-weekly-terciles-title">Tercile evolution across forecast weeks</h3>
          <span>Raw ensemble probability</span>
        </div>
        <p class="probability-panel__section-copy">Each bar shows the fraction of available members in the three climatological categories for that week.</p>
        ${weeklyTercileEvolution(outlook, variable, index, week.week)}
      </section>

      <section class="probability-panel__section" aria-labelledby="probability-additional-title">
        <h3 id="probability-additional-title">Additional probability diagnostics</h3>
        <div class="probability-panel__unavailable" role="note">
          <strong>Threshold-exceedance curve unavailable</strong>
          <p>An exceedance curve requires the selected-cell member values. The published summary contains quantiles and tercile fractions, so the curve cannot be reconstructed without inventing a distribution.</p>
        </div>
        <div class="probability-panel__unavailable" role="note">
          <strong>Member histogram unavailable</strong>
          <p>Individual member values are deliberately not sent to the browser. The exact member-derived quantiles and interval chart above remain available.</p>
        </div>
        <div class="probability-panel__unavailable" role="note">
          <strong>Weekly transition probabilities unavailable</strong>
          <p>Transitions require the same member identities to be preserved across forecast weeks. Member-level identities are not included in the published summary.</p>
        </div>
        <div class="probability-panel__unavailable" role="note">
          <strong>Probabilistic verification pending observations</strong>
          <p>Reliability, Brier scores, and rank histograms are withheld until complete matched observations are available for the forecast weeks.</p>
        </div>
      </section>

      <footer class="probability-panel__footer">
        <strong>How to interpret this</strong>
        <p>Probabilities are the fractions of available ensemble members satisfying the event. They are not necessarily calibrated event frequencies. P10–P90 is an 80% ensemble interval, not a confidence interval or a skill estimate.</p>
      </footer>
    </aside>
  `;
  host.hidden = false;
  host.querySelector<HTMLButtonElement>(".probability-panel__close")
    ?.addEventListener("click", onClose);
  host.querySelector<HTMLElement>("#probability-panel-title")
    ?.focus({ preventScroll: true });
}
