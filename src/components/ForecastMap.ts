import { colorFor, formatValue } from "../lib/color";
import type {
  ForecastData,
  ForecastWeek,
  IndiaMapGeographyData,
  ProductDefinition,
  ProductKey,
} from "../types";

const SVG_NS = "http://www.w3.org/2000/svg";
const MAP_SIZE = 620;
const LON_MIN = 59.25;
const LON_MAX = 99.75;
const LAT_MIN = -0.75;
const LAT_MAX = 39.75;
const VISUAL_GRID_SIZE = 162;
const WIND_VECTOR_STRIDE = 3;
const WIND_REFERENCE_SPEED = 5;
const WIND_REFERENCE_LENGTH = 32;

function svgElement<K extends keyof SVGElementTagNameMap>(
  tag: K,
): SVGElementTagNameMap[K] {
  return document.createElementNS(SVG_NS, tag);
}

function mapX(longitude: number): number {
  return ((longitude - LON_MIN) / (LON_MAX - LON_MIN)) * MAP_SIZE;
}

function mapY(latitude: number): number {
  return ((LAT_MAX - latitude) / (LAT_MAX - LAT_MIN)) * MAP_SIZE;
}

export class ForecastMap {
  private readonly container: HTMLElement;
  private readonly forecast: ForecastData;
  private readonly geography: IndiaMapGeographyData;
  private readonly tooltip: HTMLDivElement;

  constructor(
    container: HTMLElement,
    forecast: ForecastData,
    geography: IndiaMapGeographyData,
  ) {
    this.container = container;
    this.forecast = forecast;
    this.geography = geography;
    this.tooltip = document.createElement("div");
    this.tooltip.className = "map-tooltip";
    this.tooltip.hidden = true;
    this.container.append(this.tooltip);
  }

  render(
    productKey: ProductKey,
    week: ForecastWeek,
    product: ProductDefinition,
  ): void {
    this.container.querySelector("svg")?.remove();
    const svg = svgElement("svg");
    svg.setAttribute("viewBox", `0 0 ${MAP_SIZE} ${MAP_SIZE}`);
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      `${product.label} map for Week ${week.week}, ${week.valid_start} through ${week.valid_end}`,
    );
    svg.classList.add("forecast-map");

    const ocean = svgElement("rect");
    ocean.setAttribute("width", String(MAP_SIZE));
    ocean.setAttribute("height", String(MAP_SIZE));
    ocean.setAttribute("class", "map-ocean");
    svg.append(ocean);
    this.addInterpolatedField(svg, productKey, week, product);
    this.addWorldBoundaries(svg);
    this.addGraticules(svg);
    if (productKey === "wind850_anomaly") {
      this.addWindVectors(svg, week);
    }
    this.addInteraction(svg, productKey, week, product);
    this.addOutline(svg);
    this.addIndiaAdmin(svg);
    this.container.prepend(svg);
  }

  private addWindVectors(svg: SVGSVGElement, week: ForecastWeek): void {
    const vectors = week.vectors?.wind850_anomaly;
    if (!vectors) throw new Error(`wind vectors are unavailable for Week ${week.week}`);
    const { latitude, longitude } = this.forecast.grid;
    const expected = latitude.length * longitude.length;
    if (vectors.u.length !== expected || vectors.v.length !== expected) {
      throw new Error(`wind vectors have an invalid size for Week ${week.week}`);
    }

    const definitions = svgElement("defs");
    const marker = svgElement("marker");
    marker.setAttribute("id", `wind-arrow-${week.week}`);
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
    svg.append(definitions);

    const group = svgElement("g");
    group.setAttribute("class", "map-wind-vectors");
    for (let row = 1; row < latitude.length; row += WIND_VECTOR_STRIDE) {
      for (let column = 1; column < longitude.length; column += WIND_VECTOR_STRIDE) {
        const index = row * longitude.length + column;
        const u = vectors.u[index];
        const v = vectors.v[index];
        const magnitude = Math.hypot(u, v);
        if (!Number.isFinite(magnitude) || magnitude < 0.2) continue;
        const scale = Math.min(magnitude / WIND_REFERENCE_SPEED, 1.5);
        const length = WIND_REFERENCE_LENGTH * scale;
        const dx = (u / magnitude) * length;
        const dy = (-v / magnitude) * length;
        const x = mapX(longitude[column]);
        const y = mapY(latitude[row]);
        const line = svgElement("line");
        line.setAttribute("x1", String(x - dx / 2));
        line.setAttribute("y1", String(y - dy / 2));
        line.setAttribute("x2", String(x + dx / 2));
        line.setAttribute("y2", String(y + dy / 2));
        line.setAttribute("marker-end", `url(#wind-arrow-${week.week})`);
        line.setAttribute("class", "map-wind-vector");
        group.append(line);
      }
    }
    svg.append(group);

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
    keyLine.setAttribute("marker-end", `url(#wind-arrow-${week.week})`);
    keyLine.setAttribute("class", "map-wind-vector");
    const keyLabel = svgElement("text");
    keyLabel.setAttribute("x", "494");
    keyLabel.setAttribute("y", "43");
    keyLabel.textContent = `${WIND_REFERENCE_SPEED} m s⁻¹ anomaly`;
    key.append(background, keyLine, keyLabel);
    svg.append(key);
  }

  private addInterpolatedField(
    svg: SVGSVGElement,
    productKey: ProductKey,
    week: ForecastWeek,
    product: ProductDefinition,
  ): void {
    const values = week.fields[productKey];
    if (!values) throw new Error(`${productKey} is unavailable for Week ${week.week}`);
    const { latitude, longitude } = this.forecast.grid;
    const canvas = document.createElement("canvas");
    canvas.width = VISUAL_GRID_SIZE;
    canvas.height = VISUAL_GRID_SIZE;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas rendering is unavailable");

    const sample = (row: number, column: number): number => {
      const safeRow = Math.max(0, Math.min(latitude.length - 1, row));
      const safeColumn = Math.max(0, Math.min(longitude.length - 1, column));
      return values[safeRow * longitude.length + safeColumn];
    };

    for (let y = 0; y < VISUAL_GRID_SIZE; y += 1) {
      const lat = LAT_MAX - ((y + 0.5) / VISUAL_GRID_SIZE) * (LAT_MAX - LAT_MIN);
      const row = (latitude[0] - lat) / this.forecast.grid.spacing_degrees;
      const row0 = Math.floor(row);
      const rowWeight = row - row0;
      for (let x = 0; x < VISUAL_GRID_SIZE; x += 1) {
        const lon = LON_MIN + ((x + 0.5) / VISUAL_GRID_SIZE) * (LON_MAX - LON_MIN);
        const column = (lon - longitude[0]) / this.forecast.grid.spacing_degrees;
        const column0 = Math.floor(column);
        const columnWeight = column - column0;
        const top =
          sample(row0, column0) * (1 - columnWeight) +
          sample(row0, column0 + 1) * columnWeight;
        const bottom =
          sample(row0 + 1, column0) * (1 - columnWeight) +
          sample(row0 + 1, column0 + 1) * columnWeight;
        const value = top * (1 - rowWeight) + bottom * rowWeight;
        context.fillStyle = colorFor(value, product.legend);
        context.fillRect(x, y, 1, 1);
      }
    }

    const image = svgElement("image");
    image.setAttribute("x", "0");
    image.setAttribute("y", "0");
    image.setAttribute("width", String(MAP_SIZE));
    image.setAttribute("height", String(MAP_SIZE));
    image.setAttribute("preserveAspectRatio", "none");
    image.setAttribute("href", canvas.toDataURL("image/png"));
    image.setAttribute("class", "map-raster");
    svg.append(image);
  }

  private addGraticules(svg: SVGSVGElement): void {
    for (const longitude of [70, 80, 90, 100]) {
      const x = longitude === 100 ? MAP_SIZE - 1 : mapX(longitude);
      const line = svgElement("line");
      line.setAttribute("x1", String(x));
      line.setAttribute("x2", String(x));
      line.setAttribute("y1", "0");
      line.setAttribute("y2", String(MAP_SIZE));
      line.setAttribute("class", "map-graticule");
      svg.append(line);

      const label = svgElement("text");
      label.setAttribute("x", String(longitude === 100 ? x - 5 : x + 5));
      label.setAttribute("y", String(MAP_SIZE - 10));
      label.setAttribute("class", "map-coordinate");
      if (longitude === 100) label.setAttribute("text-anchor", "end");
      label.textContent = `${longitude}°E`;
      svg.append(label);
    }
    for (const latitude of [10, 20, 30]) {
      const line = svgElement("line");
      line.setAttribute("x1", "0");
      line.setAttribute("x2", String(MAP_SIZE));
      line.setAttribute("y1", String(mapY(latitude)));
      line.setAttribute("y2", String(mapY(latitude)));
      line.setAttribute("class", "map-graticule");
      svg.append(line);

      const label = svgElement("text");
      label.setAttribute("x", "8");
      label.setAttribute("y", String(mapY(latitude) - 7));
      label.setAttribute("class", "map-coordinate");
      label.textContent = `${latitude}°N`;
      svg.append(label);
    }
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
    svg.classList.add("forecast-map--interactive");
    const show = (event?: PointerEvent): void => {
      let latIndex = Math.floor(latitude.length / 2);
      let lonIndex = Math.floor(longitude.length / 2);
      if (event) {
        const bounds = svg.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        const y = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
        const hoveredLongitude = LON_MIN + x * (LON_MAX - LON_MIN);
        const hoveredLatitude = LAT_MAX - y * (LAT_MAX - LAT_MIN);
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
      }
      const lat = latitude[latIndex];
      const lon = longitude[lonIndex];
      const value = values[latIndex * longitude.length + lonIndex];
      const vector = productKey === "wind850_anomaly"
        ? week.vectors?.wind850_anomaly
        : undefined;
      const vectorIndex = latIndex * longitude.length + lonIndex;
      const vectorDetail = vector
        ? `<small>U ${vector.u[vectorIndex].toFixed(1)} · V ${vector.v[vectorIndex].toFixed(1)} m s⁻¹</small>`
        : "";
      this.tooltip.innerHTML = `
        <strong>${formatValue(value, product.units)}</strong>
        <span>${lat.toFixed(1)}°N · ${lon.toFixed(1)}°E</span>
        ${vectorDetail}
        <small>Native 1.5° grid cell</small>
      `;
      this.tooltip.hidden = false;
      svg.setAttribute(
        "aria-label",
        `${product.label}, Week ${week.week}; selected cell ${lat.toFixed(1)} degrees north, ${lon.toFixed(1)} degrees east: ${formatValue(value, product.units)}`,
      );
      if (event) {
        const bounds = this.container.getBoundingClientRect();
        this.tooltip.style.left = `${event.clientX - bounds.left + 14}px`;
        this.tooltip.style.top = `${event.clientY - bounds.top + 14}px`;
      } else {
        this.tooltip.style.left = "16px";
        this.tooltip.style.top = "16px";
      }
    };
    svg.addEventListener("pointermove", (event) => show(event));
    svg.addEventListener("pointerenter", (event) => show(event));
    svg.addEventListener("focus", () => show());
    svg.addEventListener("pointerleave", () => {
      this.tooltip.hidden = true;
    });
    svg.addEventListener("blur", () => {
      this.tooltip.hidden = true;
    });
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
