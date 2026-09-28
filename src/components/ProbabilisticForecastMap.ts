import type {
  EnsembleGridSummary,
  ForecastData,
  ForecastGridSelection,
  IndiaMapGeographyData,
  ProbabilityMapProduct,
  ProbabilisticVariable,
  RegionalOutlookData,
  RegionalOutlookWeek,
  TercileCategory,
} from "../types";

const SVG_NS = "http://www.w3.org/2000/svg";
const MAP_SIZE = 620;
const VISUAL_GRID_SIZE = 162;
const CATEGORIES: TercileCategory[] = [
  "below_normal",
  "near_normal",
  "above_normal",
];
const SPREAD_STOPS: Record<ProbabilisticVariable, number[]> = {
  rainfall: [0, 0.5, 2, 5, 10, 20, 30],
  temperature: [0, 0.25, 1, 2.5, 5, 8, 10],
};

const SPREAD_COLORS: Array<[number, number, number]> = [
  [247, 251, 255],
  [222, 235, 247],
  [198, 219, 239],
  [158, 202, 225],
  [107, 174, 214],
  [49, 130, 189],
  [8, 48, 107],
];

// Percentile maps deliberately reuse the fixed physical-value scales from the
// ensemble-mean products. That keeps P10, median, and P90 directly comparable
// with one another and with the existing mean maps across forecast weeks.
const PERCENTILE_STOPS: Record<ProbabilisticVariable, number[]> = {
  rainfall: [0, 1, 2, 5, 10, 20, 40, 60],
  temperature: [10, 14, 18, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42],
};

const PERCENTILE_COLORS: Record<
  ProbabilisticVariable,
  Array<[number, number, number]>
> = {
  rainfall: [
    [255, 255, 255],
    [183, 255, 184],
    [113, 242, 123],
    [36, 209, 59],
    [0, 154, 24],
    [0, 107, 18],
    [0, 61, 12],
    [0, 40, 7],
  ],
  temperature: [
    [150, 150, 198],
    [190, 190, 226],
    [255, 250, 205],
    [255, 241, 145],
    [255, 226, 113],
    [255, 202, 89],
    [255, 166, 53],
    [255, 142, 29],
    [255, 106, 0],
    [255, 58, 0],
    [235, 24, 0],
    [195, 4, 0],
    [155, 0, 0],
    [95, 0, 0],
  ],
};

const CATEGORY_MARGIN_STOPS = [0, 5, 10, 20, 30, 50, 100];
const CATEGORY_MARGIN_COLORS: Array<[number, number, number]> = [
  [247, 247, 247],
  [231, 225, 239],
  [212, 185, 218],
  [201, 148, 199],
  [223, 101, 176],
  [152, 45, 132],
  [73, 0, 106],
];

const CATEGORY_LABELS: Record<
  ProbabilisticVariable,
  Record<TercileCategory, string>
> = {
  rainfall: {
    below_normal: "Drier than normal",
    near_normal: "Near normal",
    above_normal: "Wetter than normal",
  },
  temperature: {
    below_normal: "Cooler than normal",
    near_normal: "Near normal",
    above_normal: "Warmer than normal",
  },
};

const CATEGORY_COLORS: Record<
  ProbabilisticVariable,
  Record<TercileCategory, [number, number, number]>
> = {
  rainfall: {
    below_normal: [177, 95, 38],
    near_normal: [112, 122, 132],
    above_normal: [24, 112, 142],
  },
  temperature: {
    below_normal: [43, 102, 164],
    near_normal: [112, 122, 132],
    above_normal: [194, 68, 46],
  },
};

let mapInstance = 0;

function svgElement<K extends keyof SVGElementTagNameMap>(
  tag: K,
): SVGElementTagNameMap[K] {
  return document.createElementNS(SVG_NS, tag);
}

function mixWithWhite(
  color: [number, number, number],
  strength: number,
): string {
  const clamped = Math.max(0, Math.min(1, strength));
  const whiteMix = 0.84 * (1 - clamped);
  const channels = color.map((channel) =>
    Math.round(channel * (1 - whiteMix) + 255 * whiteMix)
  );
  return `rgb(${channels.join(" ")})`;
}

function spreadColor(
  spread: number,
  variable: ProbabilisticVariable,
): string {
  const stops = SPREAD_STOPS[variable];
  const upperIndex = stops.findIndex((stop) => spread <= stop);
  if (upperIndex <= 0) return `rgb(${SPREAD_COLORS[0].join(" ")})`;
  if (upperIndex === -1) {
    return `rgb(${SPREAD_COLORS.at(-1)!.join(" ")})`;
  }
  const lowerIndex = upperIndex - 1;
  const fraction = (spread - stops[lowerIndex]) /
    (stops[upperIndex] - stops[lowerIndex]);
  const channels = SPREAD_COLORS[lowerIndex].map((channel, index) =>
    Math.round(channel + (SPREAD_COLORS[upperIndex][index] - channel) * fraction)
  );
  return `rgb(${channels.join(" ")})`;
}

function interpolateColor(
  value: number,
  stops: number[],
  colors: Array<[number, number, number]>,
): string {
  const upperIndex = stops.findIndex((stop) => value <= stop);
  if (upperIndex <= 0) return `rgb(${colors[0].join(" ")})`;
  if (upperIndex === -1) return `rgb(${colors.at(-1)!.join(" ")})`;
  const lowerIndex = upperIndex - 1;
  const fraction = (value - stops[lowerIndex]) /
    (stops[upperIndex] - stops[lowerIndex]);
  const channels = colors[lowerIndex].map((channel, index) =>
    Math.round(channel + (colors[upperIndex][index] - channel) * fraction)
  );
  return `rgb(${channels.join(" ")})`;
}

function percentileColor(
  value: number,
  variable: ProbabilisticVariable,
): string {
  return interpolateColor(
    value,
    PERCENTILE_STOPS[variable],
    PERCENTILE_COLORS[variable],
  );
}

function categoryMargin(
  probabilities: Record<TercileCategory, number | null>,
): number | null {
  if (CATEGORIES.some((category) => probabilities[category] === null)) {
    return null;
  }
  const sorted = CATEGORIES
    .map((category) => probabilities[category] as number)
    .sort((left, right) => right - left);
  return sorted[0] - sorted[1];
}

function categoryMarginColor(margin: number): string {
  return interpolateColor(
    margin,
    CATEGORY_MARGIN_STOPS,
    CATEGORY_MARGIN_COLORS,
  );
}

function leadingCategory(
  probabilities: Record<TercileCategory, number | null>,
): TercileCategory | "mixed" | null {
  if (CATEGORIES.some((category) => probabilities[category] === null)) {
    return null;
  }
  const maximum = Math.max(
    ...CATEGORIES.map((category) => probabilities[category] as number),
  );
  const winners = CATEGORIES.filter(
    (category) => Math.abs((probabilities[category] as number) - maximum) < 1e-9,
  );
  return winners.length === 1 ? winners[0] : "mixed";
}

function formatValue(value: number | null | undefined, units: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Unavailable";
  }
  return `${value.toFixed(2)} ${units}`;
}

function formatProbability(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "Unavailable";
  }
  return `${value.toFixed(value % 1 === 0 ? 0 : 1)}%`;
}

function patternColor(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  kind: "tie" | "missing",
): void {
  const stripe = (x + y) % 8 < 3;
  context.fillStyle = kind === "tie"
    ? stripe ? "#7b8793" : "#e2e5e8"
    : stripe ? "#c7cdd2" : "#f3f4f5";
  context.fillRect(x, y, 1, 1);
}

export type PercentileMapProduct = "p10" | "p50" | "p90";

function isPercentileProduct(
  product: ProbabilisticMapRenderOptions["product"],
): product is PercentileMapProduct {
  return product === "p10" || product === "p50" || product === "p90";
}

const PERCENTILE_LABELS: Record<PercentileMapProduct, string> = {
  p10: "P10 (10th percentile)",
  p50: "Median (P50)",
  p90: "P90 (90th percentile)",
};

export interface ProbabilisticMapRenderOptions {
  variable: ProbabilisticVariable;
  week: RegionalOutlookWeek;
  product:
    | ProbabilityMapProduct
    | PercentileMapProduct
    | "spread"
    | "category_margin";
  extent: "india" | "regional";
  selected?: ForecastGridSelection;
}

export class ProbabilisticForecastMap {
  private readonly container: HTMLElement;
  private readonly forecast: ForecastData;
  private readonly outlook: RegionalOutlookData;
  private readonly geography: IndiaMapGeographyData;
  private readonly onSelect?: (selection: ForecastGridSelection) => void;
  private readonly tooltip: HTMLDivElement;
  private readonly instanceId = ++mapInstance;

  constructor(
    container: HTMLElement,
    forecast: ForecastData,
    outlook: RegionalOutlookData,
    geography: IndiaMapGeographyData,
    onSelect?: (selection: ForecastGridSelection) => void,
  ) {
    this.container = container;
    this.forecast = forecast;
    this.outlook = outlook;
    this.geography = geography;
    this.onSelect = onSelect;
    this.tooltip = document.createElement("div");
    this.tooltip.className = "map-tooltip probabilistic-map-tooltip";
    this.tooltip.id = `probabilistic-map-tooltip-${this.instanceId}`;
    this.tooltip.setAttribute("role", "tooltip");
    this.tooltip.hidden = true;
  }

  render(options: ProbabilisticMapRenderOptions): void {
    this.container.replaceChildren();
    this.container.append(this.tooltip);
    const svg = svgElement("svg");
    svg.setAttribute("viewBox", `0 0 ${MAP_SIZE} ${MAP_SIZE}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-describedby", this.tooltip.id);
    svg.setAttribute("aria-keyshortcuts", "ArrowUp ArrowDown ArrowLeft ArrowRight Enter Space");
    svg.classList.add(
      "forecast-map",
      "forecast-map--interactive",
      "probabilistic-forecast-map",
    );
    const label = options.product === "spread"
      ? "ensemble spread P90 minus P10"
      : isPercentileProduct(options.product)
        ? `${PERCENTILE_LABELS[options.product]} ensemble outcome`
        : options.product === "category_margin"
          ? "category separation between the leading and second terciles"
          : options.product === "most_likely"
            ? "most likely tercile and leading member fraction"
            : `${CATEGORY_LABELS[options.variable][options.product]} probability`;
    svg.setAttribute(
      "aria-label",
      `${options.variable} ${label}, Week ${options.week.week}, ${options.extent === "regional" ? "regional grid" : "India"} extent. Use arrow keys then Enter to inspect a native grid cell.`,
    );

    const ocean = svgElement("rect");
    ocean.setAttribute("width", String(MAP_SIZE));
    ocean.setAttribute("height", String(MAP_SIZE));
    ocean.setAttribute("class", "map-ocean");
    svg.append(ocean);

    const definitions = svgElement("defs");
    const clip = svgElement("clipPath");
    const clipId = `probabilistic-india-clip-${this.instanceId}`;
    clip.setAttribute("id", clipId);
    const clipPath = svgElement("path");
    clipPath.setAttribute("d", this.geography.india_outline_path);
    clipPath.setAttribute("fill-rule", "evenodd");
    clip.append(clipPath);
    definitions.append(clip);
    svg.append(definitions);

    this.addField(svg, options, clipId);
    this.addWorldBoundaries(svg);
    this.addGraticules(svg);
    this.addOutline(svg);
    this.addIndiaAdmin(svg);
    this.addInteraction(svg, options);
    this.container.prepend(svg);
  }

  private addField(
    svg: SVGSVGElement,
    options: ProbabilisticMapRenderOptions,
    clipId: string,
  ): void {
    const { latitude, longitude, spacing_degrees: spacing } = this.outlook.grid;
    const fields = options.week.probability_fields[options.variable];
    const summary = options.week.summary_fields?.[options.variable];
    const latitudeMaximum = latitude[0] + spacing / 2;
    const latitudeMinimum = latitude.at(-1)! - spacing / 2;
    const longitudeMinimum = longitude[0] - spacing / 2;
    const longitudeMaximum = longitude.at(-1)! + spacing / 2;
    const supportMask =
      this.forecast.grid.india_mask ?? this.forecast.grid.support_mask ?? [];

    const canvas = document.createElement("canvas");
    canvas.width = VISUAL_GRID_SIZE;
    canvas.height = VISUAL_GRID_SIZE;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas rendering is unavailable");

    const sample = (
      values: Array<number | null>,
      row: number,
      column: number,
    ): number | null => {
      const safeRow = Math.max(0, Math.min(latitude.length - 1, row));
      const safeColumn = Math.max(0, Math.min(longitude.length - 1, column));
      const value = values[safeRow * longitude.length + safeColumn];
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    };

    const interpolate = (
      values: Array<number | null>,
      row: number,
      column: number,
      rowWeight: number,
      columnWeight: number,
    ): number | null => {
      const corners = [
        sample(values, row, column),
        sample(values, row, column + 1),
        sample(values, row + 1, column),
        sample(values, row + 1, column + 1),
      ];
      if (corners.some((value) => value === null)) return null;
      const [topLeft, topRight, bottomLeft, bottomRight] = corners as number[];
      const top = topLeft * (1 - columnWeight) + topRight * columnWeight;
      const bottom = bottomLeft * (1 - columnWeight) + bottomRight * columnWeight;
      return top * (1 - rowWeight) + bottom * rowWeight;
    };

    for (let y = 0; y < VISUAL_GRID_SIZE; y += 1) {
      const lat = latitudeMaximum -
        ((y + 0.5) / VISUAL_GRID_SIZE) * (latitudeMaximum - latitudeMinimum);
      const row = (latitude[0] - lat) / spacing;
      const row0 = Math.floor(row);
      const rowWeight = row - row0;
      for (let x = 0; x < VISUAL_GRID_SIZE; x += 1) {
        const lon = longitudeMinimum +
          ((x + 0.5) / VISUAL_GRID_SIZE) * (longitudeMaximum - longitudeMinimum);
        const column = (lon - longitude[0]) / spacing;
        const column0 = Math.floor(column);
        const columnWeight = column - column0;
        const nearestRow = Math.max(0, Math.min(latitude.length - 1, Math.round(row)));
        const nearestColumn = Math.max(
          0,
          Math.min(longitude.length - 1, Math.round(column)),
        );
        const supported = options.extent === "regional" || (supportMask[
          nearestRow * longitude.length + nearestColumn
        ] ?? false);
        if (!supported) {
          patternColor(context, x, y, "missing");
          continue;
        }

        if (options.product === "spread") {
          const spread = summary
            ? interpolate(
              summary.p90_minus_p10,
              row0,
              column0,
              rowWeight,
              columnWeight,
            )
            : null;
          if (spread === null) {
            patternColor(context, x, y, "missing");
            continue;
          }
          context.fillStyle = spreadColor(spread, options.variable);
          context.fillRect(x, y, 1, 1);
          continue;
        }

        if (isPercentileProduct(options.product)) {
          const percentile = summary
            ? interpolate(
              summary[options.product],
              row0,
              column0,
              rowWeight,
              columnWeight,
            )
            : null;
          if (percentile === null) {
            patternColor(context, x, y, "missing");
            continue;
          }
          context.fillStyle = percentileColor(percentile, options.variable);
          context.fillRect(x, y, 1, 1);
          continue;
        }

        const probabilities: Record<TercileCategory, number | null> = {
          below_normal: interpolate(
            fields.below_normal, row0, column0, rowWeight, columnWeight,
          ),
          near_normal: interpolate(
            fields.near_normal, row0, column0, rowWeight, columnWeight,
          ),
          above_normal: interpolate(
            fields.above_normal, row0, column0, rowWeight, columnWeight,
          ),
        };
        if (options.product === "category_margin") {
          const margin = categoryMargin(probabilities);
          if (margin === null) {
            patternColor(context, x, y, "missing");
            continue;
          }
          context.fillStyle = categoryMarginColor(margin);
          context.fillRect(x, y, 1, 1);
          continue;
        }
        if (options.product !== "most_likely") {
          const probability = probabilities[options.product];
          if (probability === null) {
            patternColor(context, x, y, "missing");
            continue;
          }
          context.fillStyle = mixWithWhite(
            CATEGORY_COLORS[options.variable][options.product],
            probability / 100,
          );
          context.fillRect(x, y, 1, 1);
          continue;
        }

        const category = leadingCategory(probabilities);
        if (category === null) {
          patternColor(context, x, y, "missing");
        } else if (category === "mixed") {
          patternColor(context, x, y, "tie");
        } else {
          context.fillStyle = mixWithWhite(
            CATEGORY_COLORS[options.variable][category],
            Math.max(0, ((probabilities[category] as number) - 33) / 67),
          );
          context.fillRect(x, y, 1, 1);
        }
      }
    }

    const image = svgElement("image");
    image.setAttribute("x", "0");
    image.setAttribute("y", "0");
    image.setAttribute("width", String(MAP_SIZE));
    image.setAttribute("height", String(MAP_SIZE));
    image.setAttribute("preserveAspectRatio", "none");
    image.setAttribute("href", canvas.toDataURL("image/png"));
    if (options.extent === "india") {
      image.setAttribute("clip-path", `url(#${clipId})`);
    }
    image.setAttribute("class", "map-raster");
    svg.append(image);
  }

  private addInteraction(
    svg: SVGSVGElement,
    options: ProbabilisticMapRenderOptions,
  ): void {
    const { latitude, longitude, spacing_degrees: spacing } = this.outlook.grid;
    const latitudeMaximum = latitude[0] + spacing / 2;
    const latitudeMinimum = latitude.at(-1)! - spacing / 2;
    const longitudeMinimum = longitude[0] - spacing / 2;
    const longitudeMaximum = longitude.at(-1)! + spacing / 2;
    const interactionSurface = svgElement("rect");
    interactionSurface.setAttribute("x", "0");
    interactionSurface.setAttribute("y", "0");
    interactionSurface.setAttribute("width", String(MAP_SIZE));
    interactionSurface.setAttribute("height", String(MAP_SIZE));
    interactionSurface.setAttribute("fill", "transparent");
    interactionSurface.setAttribute("pointer-events", "all");
    interactionSurface.setAttribute("class", "map-interaction-surface");
    svg.append(interactionSurface);

    const hoverMarker = this.marker("map-sample-marker");
    const selectedMarker = this.marker("map-location-marker");
    svg.append(selectedMarker, hoverMarker);

    let latitudeIndex = options.selected?.latitude_index ??
      Math.floor(latitude.length / 2);
    let longitudeIndex = options.selected?.longitude_index ??
      Math.floor(longitude.length / 2);
    let pinned = false;

    const positionMarker = (
      marker: SVGGElement,
      latIndex: number,
      lonIndex: number,
    ): void => {
      const x = ((longitude[lonIndex] - longitudeMinimum) /
        (longitudeMaximum - longitudeMinimum)) * MAP_SIZE;
      const y = ((latitudeMaximum - latitude[latIndex]) /
        (latitudeMaximum - latitudeMinimum)) * MAP_SIZE;
      marker.setAttribute("transform", `translate(${x} ${y})`);
      marker.setAttribute("visibility", "visible");
    };
    if (options.selected) {
      positionMarker(
        selectedMarker,
        options.selected.latitude_index,
        options.selected.longitude_index,
      );
    }

    const supported = (): boolean => {
      if (options.extent === "regional") return true;
      const mask = this.forecast.grid.india_mask ??
        this.forecast.grid.support_mask ?? [];
      return mask[latitudeIndex * longitude.length + longitudeIndex] ?? false;
    };

    const positionTooltip = (): void => {
      const x = ((longitude[longitudeIndex] - longitudeMinimum) /
        (longitudeMaximum - longitudeMinimum)) * this.container.clientWidth;
      const y = ((latitudeMaximum - latitude[latitudeIndex]) /
        (latitudeMaximum - latitudeMinimum)) * this.container.clientHeight;
      const edge = 8;
      const gap = 12;
      const maximumLeft = Math.max(
        edge,
        this.container.clientWidth - this.tooltip.offsetWidth - edge,
      );
      const maximumTop = Math.max(
        edge,
        this.container.clientHeight - this.tooltip.offsetHeight - edge,
      );
      this.tooltip.style.left = `${Math.max(
        edge,
        Math.min(maximumLeft, x + gap),
      )}px`;
      this.tooltip.style.top = `${Math.max(
        edge,
        Math.min(maximumTop, y + gap),
      )}px`;
    };

    const show = (): void => {
      const index = latitudeIndex * longitude.length + longitudeIndex;
      const lat = latitude[latitudeIndex];
      const lon = longitude[longitudeIndex];
      const fields = options.week.probability_fields[options.variable];
      const probabilities: Record<TercileCategory, number | null> = {
        below_normal: fields.below_normal[index] ?? null,
        near_normal: fields.near_normal[index] ?? null,
        above_normal: fields.above_normal[index] ?? null,
      };
      const summary = options.week.summary_fields?.[options.variable];
      const expected = this.outlook.issue.expected_members ??
        this.outlook.issue.members;
      const valid = summary?.valid_member_count[index] ?? expected;
      const reference = this.outlook.probability_definition.reference_id ??
        "Lead-matched 2002–2021 model climatology";
      if (!supported()) {
        this.tooltip.innerHTML = `
          <strong>Outside supported India cells</strong>
          <span>${lat.toFixed(1)}°N · ${lon.toFixed(1)}°E</span>
        `;
      } else if (options.product === "spread") {
        this.tooltip.innerHTML = summary
          ? `
            <strong>P90 − P10 · ${formatValue(summary.p90_minus_p10[index], summary.units)}</strong>
            <span>P10 ${formatValue(summary.p10[index], summary.units)} · Median ${formatValue(summary.p50[index], summary.units)} · P90 ${formatValue(summary.p90[index], summary.units)}</span>
            <small>Week ${options.week.week} · ${options.week.valid_start} to ${options.week.valid_end}</small>
            <small>${valid}/${expected} valid members · native ${spacing}° grid cell</small>
          `
          : `<strong>Ensemble spread unavailable</strong><span>This issue predates grid quantile summaries.</span>`;
      } else if (isPercentileProduct(options.product)) {
        const value = summary?.[options.product][index];
        this.tooltip.innerHTML = summary
          ? `
            <strong>${PERCENTILE_LABELS[options.product]} · ${formatValue(value, summary.units)}</strong>
            <span>P10 ${formatValue(summary.p10[index], summary.units)} · Median ${formatValue(summary.p50[index], summary.units)} · P90 ${formatValue(summary.p90[index], summary.units)}</span>
            <small>Week ${options.week.week} · ${options.week.valid_start} to ${options.week.valid_end}</small>
            <small>${valid}/${expected} valid members · native ${spacing}° grid cell</small>
          `
          : `<strong>${PERCENTILE_LABELS[options.product]} unavailable</strong><span>This issue predates grid quantile summaries.</span>`;
      } else if (options.product === "category_margin") {
        const margin = categoryMargin(probabilities);
        this.tooltip.innerHTML = margin === null
          ? `<strong>Category separation unavailable</strong><span>Tercile probabilities are unavailable at this grid cell.</span>`
          : `
            <strong>Category separation · ${formatProbability(margin)}</strong>
            <span>Below ${formatProbability(probabilities.below_normal)} · Near ${formatProbability(probabilities.near_normal)} · Above ${formatProbability(probabilities.above_normal)}</span>
            <small>Leading minus second-highest tercile probability</small>
            <small>Not confidence or forecast skill · Raw ensemble probabilities</small>
            <small>Week ${options.week.week} · ${options.week.valid_start} to ${options.week.valid_end}</small>
            <small>${valid}/${expected} valid members · native ${spacing}° grid cell</small>
          `;
      } else {
        const leader = summary?.leading_category[index] ??
          leadingCategory(probabilities);
        const leaderText = leader === "mixed"
          ? "No unique leading category"
          : leader
            ? CATEGORY_LABELS[options.variable][leader]
            : "Tercile probabilities unavailable";
        this.tooltip.innerHTML = `
          <strong>${leaderText}</strong>
          <span>Below ${formatProbability(probabilities.below_normal)} · Near ${formatProbability(probabilities.near_normal)} · Above ${formatProbability(probabilities.above_normal)}</span>
          <small>Week ${options.week.week} · ${options.week.valid_start} to ${options.week.valid_end}</small>
          <small>${valid}/${expected} valid members · Raw ensemble probability</small>
          <small>${reference} · native ${spacing}° grid cell</small>
        `;
      }
      this.tooltip.hidden = false;
      positionMarker(hoverMarker, latitudeIndex, longitudeIndex);
      positionTooltip();
    };

    const select = (): void => {
      if (!supported()) return;
      positionMarker(selectedMarker, latitudeIndex, longitudeIndex);
      this.onSelect?.({
        latitude_index: latitudeIndex,
        longitude_index: longitudeIndex,
        latitude: latitude[latitudeIndex],
        longitude: longitude[longitudeIndex],
        week: options.week.week,
      });
    };

    const selectFromClient = (clientX: number, clientY: number): void => {
      const bounds = interactionSurface.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (clientX - bounds.left) / bounds.width));
      const y = Math.max(0, Math.min(1, (clientY - bounds.top) / bounds.height));
      const hoveredLongitude = longitudeMinimum +
        x * (longitudeMaximum - longitudeMinimum);
      const hoveredLatitude = latitudeMaximum -
        y * (latitudeMaximum - latitudeMinimum);
      longitudeIndex = Math.max(
        0,
        Math.min(
          longitude.length - 1,
          Math.round((hoveredLongitude - longitude[0]) / spacing),
        ),
      );
      latitudeIndex = Math.max(
        0,
        Math.min(
          latitude.length - 1,
          Math.round((latitude[0] - hoveredLatitude) / spacing),
        ),
      );
      show();
    };

    interactionSurface.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch") return;
      pinned = false;
      selectFromClient(event.clientX, event.clientY);
    });
    interactionSurface.addEventListener("pointerleave", () => {
      if (!pinned && document.activeElement !== svg) {
        this.tooltip.hidden = true;
        hoverMarker.setAttribute("visibility", "hidden");
      }
    });
    interactionSurface.addEventListener("click", (event) => {
      pinned = true;
      selectFromClient(event.clientX, event.clientY);
      select();
      svg.focus({ preventScroll: true });
    });
    svg.addEventListener("focus", show);
    svg.addEventListener("keydown", (event) => {
      const movement: Record<string, [number, number]> = {
        ArrowUp: [-1, 0],
        ArrowDown: [1, 0],
        ArrowLeft: [0, -1],
        ArrowRight: [0, 1],
      };
      const delta = movement[event.key];
      if (delta) {
        event.preventDefault();
        latitudeIndex = Math.max(
          0,
          Math.min(latitude.length - 1, latitudeIndex + delta[0]),
        );
        longitudeIndex = Math.max(
          0,
          Math.min(longitude.length - 1, longitudeIndex + delta[1]),
        );
        show();
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        pinned = true;
        show();
        select();
      }
    });
    svg.addEventListener("blur", () => {
      if (!pinned) {
        this.tooltip.hidden = true;
        hoverMarker.setAttribute("visibility", "hidden");
      }
    });
  }

  private marker(className: string): SVGGElement {
    const marker = svgElement("g");
    marker.setAttribute("class", className);
    marker.setAttribute("aria-hidden", "true");
    marker.setAttribute("visibility", "hidden");
    const ring = svgElement("circle");
    ring.setAttribute("r", className === "map-location-marker" ? "10" : "8");
    ring.setAttribute("class", "map-sample-marker__ring");
    const dot = svgElement("circle");
    dot.setAttribute("r", "2.75");
    dot.setAttribute("class", "map-sample-marker__dot");
    marker.append(ring, dot);
    return marker;
  }

  private addGraticules(svg: SVGSVGElement): void {
    const { latitude, longitude, spacing_degrees: spacing } = this.outlook.grid;
    const lonMinimum = longitude[0] - spacing / 2;
    const lonMaximum = longitude.at(-1)! + spacing / 2;
    const latMaximum = latitude[0] + spacing / 2;
    const latMinimum = latitude.at(-1)! - spacing / 2;
    for (const value of [70, 80, 90]) {
      const line = svgElement("line");
      const x = ((value - lonMinimum) / (lonMaximum - lonMinimum)) * MAP_SIZE;
      line.setAttribute("x1", String(x));
      line.setAttribute("x2", String(x));
      line.setAttribute("y1", "0");
      line.setAttribute("y2", String(MAP_SIZE));
      line.setAttribute("class", "map-graticule");
      svg.append(line);
    }
    for (const value of [10, 20, 30]) {
      const line = svgElement("line");
      const y = ((latMaximum - value) / (latMaximum - latMinimum)) * MAP_SIZE;
      line.setAttribute("x1", "0");
      line.setAttribute("x2", String(MAP_SIZE));
      line.setAttribute("y1", String(y));
      line.setAttribute("y2", String(y));
      line.setAttribute("class", "map-graticule");
      svg.append(line);
    }
  }

  private addWorldBoundaries(svg: SVGSVGElement): void {
    const path = svgElement("path");
    path.setAttribute("d", this.geography.world_path);
    path.setAttribute("class", "map-world-outline");
    path.setAttribute("fill-rule", "evenodd");
    svg.append(path);
  }

  private addOutline(svg: SVGSVGElement): void {
    const path = svgElement("path");
    path.setAttribute("d", this.geography.india_outline_path);
    path.setAttribute("class", "map-outline");
    path.setAttribute("fill-rule", "evenodd");
    svg.append(path);
  }

  private addIndiaAdmin(svg: SVGSVGElement): void {
    const path = svgElement("path");
    path.setAttribute("d", this.geography.india_admin_path);
    path.setAttribute("class", "map-india-admin");
    path.setAttribute("fill-rule", "evenodd");
    svg.append(path);
  }
}
