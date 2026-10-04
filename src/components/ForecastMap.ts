import { colorFor, formatValue } from "../lib/color";
import type {
  ForecastData,
  ForecastGridSelection,
  ForecastWeek,
  IndiaMapGeographyData,
  ProductDefinition,
  ProductKey,
  WindProductKey,
} from "../types";

const SVG_NS = "http://www.w3.org/2000/svg";
const MAP_WIDTH = 620;
const AXIS_LEFT = 42;
const AXIS_BOTTOM = 30;
const WIND_VECTOR_STRIDE = 3;
const WIND_REFERENCE_SPEED: Record<WindProductKey, number> = {
  wind850_mean: 10,
  wind850_anomaly: 5,
};
const WIND_REFERENCE_LENGTH = 32;
const WIND_MINIMUM_SPEED = 0.2;
const STREAMLINE_SEED_SPACING = 52;
const STREAMLINE_STEP_LENGTH = 6;
const STREAMLINE_MAX_STEPS = 110;
const STREAMLINE_OCCUPANCY_SIZE = 18;

let forecastMapSequence = 0;

export type WindRenderingMode = "streamlines" | "arrows";

interface Point {
  x: number;
  y: number;
}

interface WindVector {
  u: number;
  v: number;
}

interface WindVectorGrid {
  latitude: number[];
  longitude: number[];
  u: number[];
  v: number[];
}

function isWindProduct(productKey: ProductKey): productKey is WindProductKey {
  return productKey === "wind850_mean" || productKey === "wind850_anomaly";
}

function svgElement<K extends keyof SVGElementTagNameMap>(
  tag: K,
): SVGElementTagNameMap[K] {
  return document.createElementNS(SVG_NS, tag);
}

function graticuleValues(minimum: number, maximum: number): number[] {
  const span = maximum - minimum;
  const steps = [1, 2, 5, 10, 20, 30, 45, 90];
  const step = steps.find((candidate) => span / candidate <= 5) ?? 90;
  const first = Math.ceil(minimum / step) * step;
  const values: number[] = [];
  for (let value = first; value <= maximum; value += step) values.push(value);
  return values;
}

function interpolateGridValue(
  values: number[],
  row: number,
  column: number,
  rowCount: number,
  columnCount: number,
): number | undefined {
  if (
    rowCount < 2 ||
    columnCount < 2 ||
    row < 0 ||
    row > rowCount - 1 ||
    column < 0 ||
    column > columnCount - 1
  ) {
    return undefined;
  }
  const row0 = Math.min(rowCount - 2, Math.floor(row));
  const column0 = Math.min(columnCount - 2, Math.floor(column));
  const rowWeight = row - row0;
  const columnWeight = column - column0;
  const topLeft = values[row0 * columnCount + column0];
  const topRight = values[row0 * columnCount + column0 + 1];
  const bottomLeft = values[(row0 + 1) * columnCount + column0];
  const bottomRight = values[(row0 + 1) * columnCount + column0 + 1];
  if (![topLeft, topRight, bottomLeft, bottomRight].every(Number.isFinite)) {
    return undefined;
  }
  const top = topLeft * (1 - columnWeight) + topRight * columnWeight;
  const bottom = bottomLeft * (1 - columnWeight) + bottomRight * columnWeight;
  return top * (1 - rowWeight) + bottom * rowWeight;
}

function sampleWindVector(
  grid: WindVectorGrid,
  point: Point,
  mapHeight: number,
  longitudeMinimum: number,
  longitudeMaximum: number,
  latitudeMinimum: number,
  latitudeMaximum: number,
): WindVector | undefined {
  const longitude = longitudeMinimum +
    (point.x / MAP_WIDTH) * (longitudeMaximum - longitudeMinimum);
  const latitude = latitudeMaximum -
    (point.y / mapHeight) * (latitudeMaximum - latitudeMinimum);
  const longitudeStep =
    (grid.longitude.at(-1)! - grid.longitude[0]) / (grid.longitude.length - 1);
  const latitudeStep =
    (grid.latitude.at(-1)! - grid.latitude[0]) / (grid.latitude.length - 1);
  if (!Number.isFinite(longitudeStep) || !Number.isFinite(latitudeStep)) {
    return undefined;
  }
  const column = Math.max(
    0,
    Math.min(
      grid.longitude.length - 1,
      (longitude - grid.longitude[0]) / longitudeStep,
    ),
  );
  const row = Math.max(
    0,
    Math.min(
      grid.latitude.length - 1,
      (latitude - grid.latitude[0]) / latitudeStep,
    ),
  );
  const u = interpolateGridValue(
    grid.u,
    row,
    column,
    grid.latitude.length,
    grid.longitude.length,
  );
  const v = interpolateGridValue(
    grid.v,
    row,
    column,
    grid.latitude.length,
    grid.longitude.length,
  );
  return u === undefined || v === undefined ? undefined : { u, v };
}

function pointInsideMap(point: Point, mapHeight: number): boolean {
  return (
    point.x >= 0 &&
    point.x <= MAP_WIDTH &&
    point.y >= 0 &&
    point.y <= mapHeight
  );
}

function occupancyKey(point: Point): string {
  return `${Math.floor(point.x / STREAMLINE_OCCUPANCY_SIZE)}:${Math.floor(point.y / STREAMLINE_OCCUPANCY_SIZE)}`;
}

function traceStreamlineDirection(
  seed: Point,
  direction: -1 | 1,
  grid: WindVectorGrid,
  mapHeight: number,
  longitudeMinimum: number,
  longitudeMaximum: number,
  latitudeMinimum: number,
  latitudeMaximum: number,
  occupied: ReadonlySet<string>,
): Point[] {
  const points = [seed];
  const visited = new Set<string>([occupancyKey(seed)]);
  let previousCell = occupancyKey(seed);

  const projectedDirection = (point: Point): Point | undefined => {
    const vector = sampleWindVector(
      grid,
      point,
      mapHeight,
      longitudeMinimum,
      longitudeMaximum,
      latitudeMinimum,
      latitudeMaximum,
    );
    if (!vector) return undefined;
    const magnitude = Math.hypot(vector.u, vector.v);
    if (!Number.isFinite(magnitude) || magnitude < WIND_MINIMUM_SPEED) {
      return undefined;
    }
    const projectedU =
      vector.u * MAP_WIDTH / (longitudeMaximum - longitudeMinimum);
    const projectedV =
      vector.v * mapHeight / (latitudeMaximum - latitudeMinimum);
    const projectedMagnitude = Math.hypot(projectedU, projectedV);
    if (!Number.isFinite(projectedMagnitude) || projectedMagnitude === 0) {
      return undefined;
    }
    return {
      x: direction * projectedU / projectedMagnitude,
      y: direction * -projectedV / projectedMagnitude,
    };
  };

  for (let step = 0; step < STREAMLINE_MAX_STEPS; step += 1) {
    const current = points.at(-1)!;
    const initialDirection = projectedDirection(current);
    if (!initialDirection) break;
    const midpoint = {
      x: current.x + initialDirection.x * STREAMLINE_STEP_LENGTH / 2,
      y: current.y + initialDirection.y * STREAMLINE_STEP_LENGTH / 2,
    };
    if (!pointInsideMap(midpoint, mapHeight)) break;
    const midpointDirection = projectedDirection(midpoint);
    if (!midpointDirection) break;
    const next = {
      x: current.x + midpointDirection.x * STREAMLINE_STEP_LENGTH,
      y: current.y + midpointDirection.y * STREAMLINE_STEP_LENGTH,
    };
    if (!pointInsideMap(next, mapHeight)) break;

    const nextCell = occupancyKey(next);
    if (occupied.has(nextCell)) break;
    if (nextCell !== previousCell && visited.has(nextCell)) break;
    points.push(next);
    visited.add(nextCell);
    previousCell = nextCell;
  }
  return points;
}

function buildWindStreamlines(
  grid: WindVectorGrid,
  mapHeight: number,
  longitudeMinimum: number,
  longitudeMaximum: number,
  latitudeMinimum: number,
  latitudeMaximum: number,
): Point[][] {
  const streamlines: Point[][] = [];
  const occupied = new Set<string>();
  for (
    let y = STREAMLINE_SEED_SPACING / 2;
    y < mapHeight;
    y += STREAMLINE_SEED_SPACING
  ) {
    for (
      let x = STREAMLINE_SEED_SPACING / 2;
      x < MAP_WIDTH;
      x += STREAMLINE_SEED_SPACING
    ) {
      const seed = { x, y };
      if (occupied.has(occupancyKey(seed))) continue;
      const backward = traceStreamlineDirection(
        seed,
        -1,
        grid,
        mapHeight,
        longitudeMinimum,
        longitudeMaximum,
        latitudeMinimum,
        latitudeMaximum,
        occupied,
      );
      const forward = traceStreamlineDirection(
        seed,
        1,
        grid,
        mapHeight,
        longitudeMinimum,
        longitudeMaximum,
        latitudeMinimum,
        latitudeMaximum,
        occupied,
      );
      const points = backward.reverse().concat(forward.slice(1));
      if (points.length < 4) continue;
      streamlines.push(points);
      points.forEach((point) => occupied.add(occupancyKey(point)));
    }
  }
  return streamlines;
}

function pathData(points: Point[]): string {
  return points
    .map((point, index) =>
      `${index === 0 ? "M" : "L"}${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(" ");
}

export class ForecastMap {
  private readonly container: HTMLElement;
  private readonly forecast: ForecastData;
  private readonly geography: IndiaMapGeographyData;
  private readonly tooltip: HTMLDivElement;
  private readonly longitudeMinimum: number;
  private readonly longitudeMaximum: number;
  private readonly latitudeMinimum: number;
  private readonly latitudeMaximum: number;
  private readonly mapHeight: number;
  private readonly instanceId: number;
  private readonly onSelect?: (selection: ForecastGridSelection) => void;
  private readonly selected?: ForecastGridSelection;

  constructor(
    container: HTMLElement,
    forecast: ForecastData,
    geography: IndiaMapGeographyData,
    onSelect?: (selection: ForecastGridSelection) => void,
    selected?: ForecastGridSelection,
  ) {
    this.container = container;
    this.forecast = forecast;
    this.geography = geography;
    this.onSelect = onSelect;
    this.selected = selected;
    const { latitude, longitude, spacing_degrees: spacing } = forecast.grid;
    this.longitudeMinimum = longitude[0] - spacing / 2;
    this.longitudeMaximum = longitude.at(-1)! + spacing / 2;
    this.latitudeMaximum = latitude[0] + spacing / 2;
    this.latitudeMinimum = latitude.at(-1)! - spacing / 2;
    const aspect =
      (this.latitudeMaximum - this.latitudeMinimum) /
      (this.longitudeMaximum - this.longitudeMinimum);
    this.mapHeight = Math.max(260, Math.min(760, Math.round(MAP_WIDTH * aspect)));
    this.instanceId = ++forecastMapSequence;
    this.tooltip = document.createElement("div");
    this.tooltip.className = "map-tooltip";
    this.tooltip.id = `forecast-map-tooltip-${this.instanceId}`;
    this.tooltip.setAttribute("role", "tooltip");
    this.tooltip.hidden = true;
    this.container.append(this.tooltip);
  }

  render(
    productKey: ProductKey,
    week: ForecastWeek,
    product: ProductDefinition,
    windRenderingMode: WindRenderingMode = "streamlines",
  ): void {
    this.container.querySelector("svg")?.remove();
    const svg = svgElement("svg");
    svg.setAttribute(
      "viewBox",
      `0 0 ${AXIS_LEFT + MAP_WIDTH} ${this.mapHeight + AXIS_BOTTOM}`,
    );
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      `${product.label} map for Week ${week.week}, ${week.valid_start} through ${week.valid_end}`,
    );
    svg.classList.add("forecast-map");

    const definitions = svgElement("defs");
    const clipPath = svgElement("clipPath");
    const clipPathId = `forecast-map-plot-${this.instanceId}`;
    clipPath.setAttribute("id", clipPathId);
    clipPath.setAttribute("clipPathUnits", "userSpaceOnUse");
    const clipRectangle = svgElement("rect");
    clipRectangle.setAttribute("width", String(MAP_WIDTH));
    clipRectangle.setAttribute("height", String(this.mapHeight));
    clipPath.append(clipRectangle);
    definitions.append(clipPath);
    svg.append(definitions);

    const plot = svgElement("g");
    plot.setAttribute("class", "forecast-map__plot");
    plot.setAttribute("transform", `translate(${AXIS_LEFT} 0)`);
    plot.setAttribute("clip-path", `url(#${clipPathId})`);
    svg.append(plot);

    const ocean = svgElement("rect");
    ocean.setAttribute("width", String(MAP_WIDTH));
    ocean.setAttribute("height", String(this.mapHeight));
    ocean.setAttribute("class", "map-ocean");
    plot.append(ocean);
    this.addInterpolatedField(plot, productKey, week, product);
    this.addWorldBoundaries(plot);
    this.addGraticules(plot, svg);
    if (isWindProduct(productKey)) {
      if (windRenderingMode === "arrows") {
        this.addWindVectors(svg, plot, productKey, week);
      } else {
        this.addWindStreamlines(svg, plot, productKey, week);
      }
    }
    this.addOutline(plot);
    this.addIndiaAdmin(plot);
    this.addInteraction(svg, productKey, week, product);
    this.container.prepend(svg);
  }

  private addWindMarker(svg: SVGSVGElement, markerId: string): void {
    const definitions = svg.querySelector("defs");
    if (!definitions) throw new Error("SVG definitions are unavailable");
    const marker = svgElement("marker");
    marker.setAttribute("id", markerId);
    marker.setAttribute("viewBox", "0 0 8 8");
    marker.setAttribute("refX", "7");
    marker.setAttribute("refY", "4");
    marker.setAttribute("markerWidth", "5");
    marker.setAttribute("markerHeight", "5");
    marker.setAttribute("orient", "auto-start-reverse");
    const head = svgElement("path");
    head.setAttribute("d", "M 0 0 L 8 4 L 0 8 z");
    head.setAttribute("class", "map-wind-arrowhead");
    marker.append(head);
    definitions.append(marker);
  }

  private validWindVectors(
    productKey: WindProductKey,
    week: ForecastWeek,
  ): WindVectorGrid | undefined {
    const vectors = week.vectors?.[productKey];
    if (!vectors) return undefined;
    const { latitude, longitude } = this.forecast.grid;
    const expected = latitude.length * longitude.length;
    if (vectors.u.length !== expected || vectors.v.length !== expected) {
      throw new Error(`wind vectors have an invalid size for Week ${week.week}`);
    }
    return { latitude, longitude, u: vectors.u, v: vectors.v };
  }

  private addWindVectors(
    svg: SVGSVGElement,
    plot: SVGGElement,
    productKey: WindProductKey,
    week: ForecastWeek,
  ): void {
    const vectors = this.validWindVectors(productKey, week);
    if (!vectors) return;
    const { latitude, longitude } = vectors;
    const referenceSpeed = WIND_REFERENCE_SPEED[productKey];
    const markerId = `forecast-map-wind-arrow-${this.instanceId}`;
    this.addWindMarker(svg, markerId);

    const group = svgElement("g");
    group.setAttribute("class", "map-wind-vectors");
    for (let row = 1; row < latitude.length; row += WIND_VECTOR_STRIDE) {
      for (let column = 1; column < longitude.length; column += WIND_VECTOR_STRIDE) {
        const index = row * longitude.length + column;
        const u = vectors.u[index];
        const v = vectors.v[index];
        const magnitude = Math.hypot(u, v);
        if (!Number.isFinite(magnitude) || magnitude < WIND_MINIMUM_SPEED) continue;
        const scale = Math.min(magnitude / referenceSpeed, 1.5);
        const length = WIND_REFERENCE_LENGTH * scale;
        const dx = (u / magnitude) * length;
        const dy = (-v / magnitude) * length;
        const x = this.mapX(longitude[column]);
        const y = this.mapY(latitude[row]);
        const line = svgElement("line");
        line.setAttribute("x1", String(x - dx / 2));
        line.setAttribute("y1", String(y - dy / 2));
        line.setAttribute("x2", String(x + dx / 2));
        line.setAttribute("y2", String(y + dy / 2));
        line.setAttribute("marker-end", `url(#${markerId})`);
        line.setAttribute("class", "map-wind-vector");
        group.append(line);
      }
    }
    plot.append(group);

    const key = svgElement("g");
    key.setAttribute("class", "map-wind-key");
    const background = svgElement("rect");
    background.setAttribute("x", "438");
    background.setAttribute("y", "18");
    background.setAttribute("width", "164");
    background.setAttribute("height", "42");
    const keyLine = svgElement("line");
    keyLine.setAttribute("x1", "452");
    keyLine.setAttribute("y1", "39");
    keyLine.setAttribute("x2", String(452 + WIND_REFERENCE_LENGTH));
    keyLine.setAttribute("y2", "39");
    keyLine.setAttribute("marker-end", `url(#${markerId})`);
    keyLine.setAttribute("class", "map-wind-vector");
    const keyLabel = svgElement("text");
    keyLabel.setAttribute("x", "494");
    keyLabel.setAttribute("y", "43");
    keyLabel.textContent = `${referenceSpeed} m s⁻¹${productKey === "wind850_anomaly" ? " anomaly" : ""}`;
    key.append(background, keyLine, keyLabel);
    plot.append(key);
  }

  private addWindStreamlines(
    svg: SVGSVGElement,
    plot: SVGGElement,
    productKey: WindProductKey,
    week: ForecastWeek,
  ): void {
    const vectors = this.validWindVectors(productKey, week);
    if (!vectors) return;
    const markerId = `forecast-map-wind-streamline-${this.instanceId}`;
    this.addWindMarker(svg, markerId);
    const streamlines = buildWindStreamlines(
      vectors,
      this.mapHeight,
      this.longitudeMinimum,
      this.longitudeMaximum,
      this.latitudeMinimum,
      this.latitudeMaximum,
    );
    const group = svgElement("g");
    group.setAttribute("class", "map-wind-streamlines map-wind-vectors");
    for (const points of streamlines) {
      const path = svgElement("path");
      path.setAttribute("d", pathData(points));
      path.setAttribute("fill", "none");
      path.setAttribute("class", "map-wind-streamline map-wind-vector");
      group.append(path);

      const midpoint = Math.floor(points.length / 2);
      const start = points[Math.max(0, midpoint - 1)];
      const end = points[Math.min(points.length - 1, midpoint + 1)];
      const direction = svgElement("line");
      direction.setAttribute("x1", start.x.toFixed(1));
      direction.setAttribute("y1", start.y.toFixed(1));
      direction.setAttribute("x2", end.x.toFixed(1));
      direction.setAttribute("y2", end.y.toFixed(1));
      direction.setAttribute("marker-end", `url(#${markerId})`);
      direction.setAttribute(
        "class",
        "map-wind-streamline-direction map-wind-vector",
      );
      group.append(direction);
    }
    plot.append(group);

    const key = svgElement("g");
    key.setAttribute("class", "map-wind-key map-wind-key--streamlines");
    const background = svgElement("rect");
    background.setAttribute("x", "412");
    background.setAttribute("y", "18");
    background.setAttribute("width", "190");
    background.setAttribute("height", "42");
    const keyLine = svgElement("line");
    keyLine.setAttribute("x1", "426");
    keyLine.setAttribute("y1", "39");
    keyLine.setAttribute("x2", "462");
    keyLine.setAttribute("y2", "39");
    keyLine.setAttribute("marker-end", `url(#${markerId})`);
    keyLine.setAttribute("class", "map-wind-streamline-direction map-wind-vector");
    const keyLabel = svgElement("text");
    keyLabel.setAttribute("x", "474");
    keyLabel.setAttribute("y", "43");
    keyLabel.textContent = productKey === "wind850_anomaly"
      ? "Anomaly flow direction"
      : "Mean flow direction";
    key.append(background, keyLine, keyLabel);
    plot.append(key);
  }

  private addInterpolatedField(
    plot: SVGGElement,
    productKey: ProductKey,
    week: ForecastWeek,
    product: ProductDefinition,
  ): void {
    const values = week.fields[productKey];
    if (!values) throw new Error(`${productKey} is unavailable for Week ${week.week}`);
    const { latitude, longitude } = this.forecast.grid;
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(2, (longitude.length - 1) * 6);
    canvas.height = Math.max(2, (latitude.length - 1) * 6);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas rendering is unavailable");

    const sample = (row: number, column: number): number | null => {
      const safeRow = Math.max(0, Math.min(latitude.length - 1, row));
      const safeColumn = Math.max(0, Math.min(longitude.length - 1, column));
      return values[safeRow * longitude.length + safeColumn];
    };

    for (let y = 0; y < canvas.height; y += 1) {
      const lat = this.latitudeMaximum -
        ((y + 0.5) / canvas.height) *
        (this.latitudeMaximum - this.latitudeMinimum);
      const row = (latitude[0] - lat) / this.forecast.grid.spacing_degrees;
      const row0 = Math.floor(row);
      const rowWeight = row - row0;
      for (let x = 0; x < canvas.width; x += 1) {
        const lon = this.longitudeMinimum +
          ((x + 0.5) / canvas.width) *
          (this.longitudeMaximum - this.longitudeMinimum);
        const column = (lon - longitude[0]) / this.forecast.grid.spacing_degrees;
        const column0 = Math.floor(column);
        const columnWeight = column - column0;
        const corners = [
          sample(row0, column0),
          sample(row0, column0 + 1),
          sample(row0 + 1, column0),
          sample(row0 + 1, column0 + 1),
        ];
        const finite = corners.every(
          (candidate): candidate is number =>
            typeof candidate === "number" && Number.isFinite(candidate),
        );
        const top = finite
          ? corners[0] * (1 - columnWeight) + corners[1] * columnWeight
          : Number.NaN;
        const bottom = finite
          ? corners[2] * (1 - columnWeight) + corners[3] * columnWeight
          : Number.NaN;
        const value = top * (1 - rowWeight) + bottom * rowWeight;
        context.fillStyle = Number.isFinite(value)
          ? colorFor(value, product.legend)
          : (x + y) % 8 < 4 ? "#c7cdd2" : "#f3f4f5";
        context.fillRect(x, y, 1, 1);
      }
    }

    const image = svgElement("image");
    image.setAttribute("x", "0");
    image.setAttribute("y", "0");
    image.setAttribute("width", String(MAP_WIDTH));
    image.setAttribute("height", String(this.mapHeight));
    image.setAttribute("preserveAspectRatio", "none");
    image.setAttribute("href", canvas.toDataURL("image/png"));
    image.setAttribute("class", "map-raster");
    plot.append(image);
  }

  private addGraticules(plot: SVGGElement, svg: SVGSVGElement): void {
    const axes = svgElement("g");
    axes.setAttribute("class", "map-coordinate-axes");
    for (const longitude of graticuleValues(
      this.longitudeMinimum,
      this.longitudeMaximum,
    )) {
      const x = this.mapX(longitude);
      const line = svgElement("line");
      line.setAttribute("x1", String(x));
      line.setAttribute("x2", String(x));
      line.setAttribute("y1", "0");
      line.setAttribute("y2", String(this.mapHeight));
      line.setAttribute("class", "map-graticule");
      plot.append(line);

      const label = svgElement("text");
      label.setAttribute("x", String(AXIS_LEFT + x));
      label.setAttribute("y", String(this.mapHeight + 20));
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("class", "map-coordinate map-coordinate--longitude");
      label.textContent = `${Math.abs(longitude)}°${longitude < 0 ? "W" : "E"}`;
      axes.append(label);
    }
    for (const latitude of graticuleValues(
      this.latitudeMinimum,
      this.latitudeMaximum,
    )) {
      const line = svgElement("line");
      line.setAttribute("x1", "0");
      line.setAttribute("x2", String(MAP_WIDTH));
      line.setAttribute("y1", String(this.mapY(latitude)));
      line.setAttribute("y2", String(this.mapY(latitude)));
      line.setAttribute("class", "map-graticule");
      plot.append(line);

      const label = svgElement("text");
      label.setAttribute("x", String(AXIS_LEFT - 8));
      label.setAttribute("y", String(this.mapY(latitude) + 3));
      label.setAttribute("text-anchor", "end");
      label.setAttribute("class", "map-coordinate map-coordinate--latitude");
      label.textContent = `${Math.abs(latitude)}°${latitude < 0 ? "S" : "N"}`;
      axes.append(label);
    }
    svg.append(axes);
  }

  private addInteraction(
    svg: SVGSVGElement,
    productKey: ProductKey,
    week: ForecastWeek,
    product: ProductDefinition,
  ): void {
    const values = week.fields[productKey];
    if (!values) throw new Error(`${productKey} is unavailable for Week ${week.week}`);
    const { latitude, longitude } = this.forecast.grid;
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-describedby", this.tooltip.id);
    svg.setAttribute(
      "aria-keyshortcuts",
      "ArrowUp ArrowDown ArrowLeft ArrowRight Enter Space",
    );
    svg.classList.add("forecast-map--interactive");
    const interactionSurface = svgElement("rect");
    interactionSurface.setAttribute("x", String(AXIS_LEFT));
    interactionSurface.setAttribute("y", "0");
    interactionSurface.setAttribute("width", String(MAP_WIDTH));
    interactionSurface.setAttribute("height", String(this.mapHeight));
    interactionSurface.setAttribute("fill", "transparent");
    interactionSurface.setAttribute("pointer-events", "all");
    interactionSurface.setAttribute("aria-hidden", "true");
    interactionSurface.setAttribute("class", "map-interaction-surface");
    svg.append(interactionSurface);

    const marker = svgElement("g");
    marker.setAttribute("class", "map-sample-marker");
    marker.setAttribute("aria-hidden", "true");
    marker.setAttribute("visibility", "hidden");
    const markerRing = svgElement("circle");
    markerRing.setAttribute("r", "8");
    markerRing.setAttribute("class", "map-sample-marker__ring");
    const markerDot = svgElement("circle");
    markerDot.setAttribute("r", "2.75");
    markerDot.setAttribute("class", "map-sample-marker__dot");
    marker.append(markerRing, markerDot);
    svg.append(marker);

    const selectedMarker = svgElement("g");
    selectedMarker.setAttribute("class", "map-location-marker");
    selectedMarker.setAttribute("aria-hidden", "true");
    selectedMarker.setAttribute("visibility", "hidden");
    const selectedRing = svgElement("circle");
    selectedRing.setAttribute("r", "10");
    selectedRing.setAttribute("class", "map-sample-marker__ring");
    const selectedDot = svgElement("circle");
    selectedDot.setAttribute("r", "2.75");
    selectedDot.setAttribute("class", "map-sample-marker__dot");
    selectedMarker.append(selectedRing, selectedDot);
    svg.append(selectedMarker);

    let latIndex = this.selected?.latitude_index ?? Math.floor(latitude.length / 2);
    let lonIndex = this.selected?.longitude_index ?? Math.floor(longitude.length / 2);
    let pinnedSelection = false;
    let tapCandidate:
      | { pointerId: number; x: number; y: number }
      | undefined;

    const hide = (): void => {
      this.tooltip.hidden = true;
      marker.setAttribute("visibility", "hidden");
    };

    const positionTooltip = (lat: number, lon: number): void => {
      const surfaceBounds = interactionSurface.getBoundingClientRect();
      const containerBounds = this.container.getBoundingClientRect();
      const anchorX = surfaceBounds.left - containerBounds.left +
        ((lon - this.longitudeMinimum) /
          (this.longitudeMaximum - this.longitudeMinimum)) * surfaceBounds.width;
      const anchorY = surfaceBounds.top - containerBounds.top +
        ((this.latitudeMaximum - lat) /
          (this.latitudeMaximum - this.latitudeMinimum)) * surfaceBounds.height;
      const gap = 12;
      const edge = 8;
      const tooltipWidth = this.tooltip.offsetWidth;
      const tooltipHeight = this.tooltip.offsetHeight;
      const maximumLeft = Math.max(
        edge,
        this.container.clientWidth - tooltipWidth - edge,
      );
      const maximumTop = Math.max(
        edge,
        this.container.clientHeight - tooltipHeight - edge,
      );
      const preferredLeft = anchorX + gap + tooltipWidth <= this.container.clientWidth - edge
        ? anchorX + gap
        : anchorX - tooltipWidth - gap;
      const preferredTop = anchorY + gap + tooltipHeight <= this.container.clientHeight - edge
        ? anchorY + gap
        : anchorY - tooltipHeight - gap;
      this.tooltip.style.left = `${Math.max(edge, Math.min(maximumLeft, preferredLeft))}px`;
      this.tooltip.style.top = `${Math.max(edge, Math.min(maximumTop, preferredTop))}px`;
    };

    const positionSelectedMarker = (): void => {
      const lat = latitude[latIndex];
      const lon = longitude[lonIndex];
      selectedMarker.setAttribute(
        "transform",
        `translate(${AXIS_LEFT + this.mapX(lon)} ${this.mapY(lat)})`,
      );
      selectedMarker.setAttribute("visibility", "visible");
    };
    if (this.selected) positionSelectedMarker();

    const show = (): void => {
      const lat = latitude[latIndex];
      const lon = longitude[lonIndex];
      const value = values[latIndex * longitude.length + lonIndex];
      const vector = isWindProduct(productKey)
        ? week.vectors?.[productKey]
        : undefined;
      const vectorIndex = latIndex * longitude.length + lonIndex;
      const vectorU = vector?.u[vectorIndex];
      const vectorV = vector?.v[vectorIndex];
      const vectorDetail =
        typeof vectorU === "number" &&
        typeof vectorV === "number" &&
        Number.isFinite(vectorU) &&
        Number.isFinite(vectorV)
        ? `<small>U ${vectorU.toFixed(1)} · V ${vectorV.toFixed(1)} m s⁻¹</small>`
        : "";
      const formattedValue = typeof value === "number" && Number.isFinite(value)
        ? formatValue(value, product.units)
        : "Unavailable";
      const isExtremeProduct = productKey.endsWith("_efi") || productKey.includes("_sot_");
      const extremeVariable = isExtremeProduct && productKey.startsWith("rainfall_")
        ? "rainfall"
        : isExtremeProduct && productKey.startsWith("temperature_")
          ? "temperature"
          : undefined;
      const extremeDetail = extremeVariable && this.forecast.extreme_definition
        ? (() => {
          const efi = week.fields[`${extremeVariable}_efi` as ProductKey]?.[vectorIndex];
          const upper = week.fields[`${extremeVariable}_sot_upper` as ProductKey]?.[vectorIndex];
          const lower = extremeVariable === "temperature"
            ? week.fields.temperature_sot_lower?.[vectorIndex]
            : undefined;
          const display = (candidate: number | null | undefined): string =>
            typeof candidate === "number" && Number.isFinite(candidate)
              ? candidate.toFixed(2)
              : "Unavailable";
          return `
            <small>${week.valid_start} – ${week.valid_end}</small>
            <small>EFI ${display(efi)} · Upper SOT ${display(upper)}${extremeVariable === "temperature" ? ` · Lower SOT ${display(lower)}` : ""}</small>
            <small>${week.extreme_samples?.forecast_valid_member_count[vectorIndex] ?? "—"} forecast members · ${week.extreme_samples?.climate_valid_sample_count[vectorIndex] ?? "—"} climate samples</small>
            <small>Reference ${this.forecast.extreme_definition.reference_id}</small>
          `;
        })()
        : "";
      this.tooltip.innerHTML = `
        <strong>${formattedValue}</strong>
        <span>${lat.toFixed(1)}°N · ${lon.toFixed(1)}°E</span>
        ${vectorDetail}
        ${extremeDetail}
        <small>Native ${this.forecast.grid.spacing_degrees}° grid cell</small>
      `;
      this.tooltip.hidden = false;
      marker.setAttribute(
        "transform",
        `translate(${AXIS_LEFT + this.mapX(lon)} ${this.mapY(lat)})`,
      );
      marker.setAttribute("visibility", "visible");
      positionTooltip(lat, lon);
      svg.setAttribute(
        "aria-label",
        `${product.label}, Week ${week.week}; selected cell ${lat.toFixed(1)} degrees north, ${lon.toFixed(1)} degrees east: ${formattedValue}. Use arrow keys to inspect nearby grid cells.`,
      );
    };

    const commitSelection = (): void => {
      const index = latIndex * longitude.length + lonIndex;
      const supportMask = this.forecast.grid.india_mask ??
        this.forecast.grid.support_mask ?? [];
      if (!(supportMask[index] ?? true)) return;
      positionSelectedMarker();
      this.onSelect?.({
        latitude_index: latIndex,
        longitude_index: lonIndex,
        latitude: latitude[latIndex],
        longitude: longitude[lonIndex],
        week: week.week,
      });
    };

    const selectFromPointer = (event: Pick<PointerEvent, "clientX" | "clientY">): void => {
      const bounds = interactionSurface.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
      const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
      const hoveredLongitude = this.longitudeMinimum +
        x * (this.longitudeMaximum - this.longitudeMinimum);
      const hoveredLatitude = this.latitudeMaximum -
        y * (this.latitudeMaximum - this.latitudeMinimum);
      lonIndex = Math.max(
        0,
        Math.min(
          longitude.length - 1,
          Math.round((hoveredLongitude - longitude[0]) / this.forecast.grid.spacing_degrees),
        ),
      );
      latIndex = Math.max(
        0,
        Math.min(
          latitude.length - 1,
          Math.round((latitude[0] - hoveredLatitude) / this.forecast.grid.spacing_degrees),
        ),
      );
      show();
    };

    interactionSurface.addEventListener("pointermove", (event) => {
      if (tapCandidate?.pointerId === event.pointerId) {
        const movement = Math.hypot(
          event.clientX - tapCandidate.x,
          event.clientY - tapCandidate.y,
        );
        if (movement > 8) {
          tapCandidate = undefined;
          pinnedSelection = false;
          if (document.activeElement !== svg) hide();
        }
        if (event.pointerType === "touch" || event.buttons > 0) return;
      }
      if (event.pointerType === "touch") return;
      pinnedSelection = false;
      selectFromPointer(event);
    });
    interactionSurface.addEventListener("pointerenter", (event) => {
      if (event.pointerType !== "touch") selectFromPointer(event);
    });
    interactionSurface.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "touch" && event.pointerType !== "pen") return;
      tapCandidate = {
        pointerId: event.pointerId,
        x: event.clientX,
        y: event.clientY,
      };
    });
    interactionSurface.addEventListener("pointerup", (event) => {
      if (tapCandidate?.pointerId !== event.pointerId) return;
      const movement = Math.hypot(
        event.clientX - tapCandidate.x,
        event.clientY - tapCandidate.y,
      );
      tapCandidate = undefined;
      if (movement > 8) return;
      pinnedSelection = true;
      selectFromPointer(event);
      svg.focus({ preventScroll: true });
    });
    interactionSurface.addEventListener("click", (event) => {
      pinnedSelection = true;
      selectFromPointer(event);
      commitSelection();
    });
    interactionSurface.addEventListener("pointercancel", () => {
      tapCandidate = undefined;
      pinnedSelection = false;
      if (document.activeElement !== svg) hide();
    });
    svg.addEventListener("focus", () => show());
    interactionSurface.addEventListener("pointerleave", () => {
      if (!pinnedSelection && document.activeElement !== svg) hide();
    });
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
        pinnedSelection = false;
        latIndex = Math.max(0, Math.min(latitude.length - 1, latIndex + delta[0]));
        lonIndex = Math.max(0, Math.min(longitude.length - 1, lonIndex + delta[1]));
        show();
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        pinnedSelection = true;
        show();
        commitSelection();
      }
    });
    svg.addEventListener("blur", () => {
      tapCandidate = undefined;
      pinnedSelection = false;
      hide();
    });
  }

  private mapX(longitude: number): number {
    return (
      ((longitude - this.longitudeMinimum) /
        (this.longitudeMaximum - this.longitudeMinimum)) *
      MAP_WIDTH
    );
  }

  private mapY(latitude: number): number {
    return (
      ((this.latitudeMaximum - latitude) /
        (this.latitudeMaximum - this.latitudeMinimum)) *
      this.mapHeight
    );
  }

  private addWorldBoundaries(plot: SVGGElement): void {
    if (!this.geography.world_path) return;
    const path = svgElement("path");
    path.setAttribute("d", this.geography.world_path);
    path.setAttribute("class", "map-world-outline");
    path.setAttribute("fill-rule", "evenodd");
    plot.append(path);
  }

  private addOutline(plot: SVGGElement): void {
    if (!this.geography.india_outline_path) return;
    const path = svgElement("path");
    path.setAttribute("d", this.geography.india_outline_path);
    path.setAttribute("class", "map-outline");
    path.setAttribute("fill-rule", "evenodd");
    plot.append(path);
  }

  private addIndiaAdmin(plot: SVGGElement): void {
    if (!this.geography.india_admin_path) return;
    const path = svgElement("path");
    path.setAttribute("d", this.geography.india_admin_path);
    path.setAttribute("class", "map-india-admin");
    path.setAttribute("fill-rule", "evenodd");
    plot.append(path);
  }
}
