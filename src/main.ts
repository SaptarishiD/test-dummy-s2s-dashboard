import "./styles/main.css";
import { renderForecastPage } from "./pages/forecast";
import { renderGlobalPage } from "./pages/global";
import type {
  AppData,
  GlobalForecastData,
  GlobalMetadata,
  GlobalVariableKey,
} from "./types";

type Route = "forecast" | "india";

const ROUTES = new Set<Route>(["forecast", "india"]);
let routeCleanup: (() => void) | undefined;

function currentRoute(): Route {
  const hash = window.location.hash.replace("#", "") as Route;
  return ROUTES.has(hash) ? hash : "forecast";
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function fetchGlobalData(metadata: GlobalMetadata): Promise<GlobalForecastData> {
  const fetchBinary = async (
    path: string,
    sizeBytes: number,
    expectedSha256: string,
  ): Promise<ArrayBuffer> => {
    const response = await fetch(`./data/global/${path}`);
    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`);
    }
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength !== sizeBytes) {
      throw new Error(`${path} has an unexpected byte length`);
    }
    if (await sha256Hex(buffer) !== expectedSha256) {
      throw new Error(`${path} failed its SHA-256 check`);
    }
    return buffer;
  };
  const fields: GlobalForecastData["fields"] = {};
  const anomalies: GlobalForecastData["anomalies"] = {};
  const spreads: GlobalForecastData["spreads"] = {};
  const vectors: GlobalForecastData["vectors"] = {};
  const loading: Partial<Record<GlobalVariableKey, Promise<void>>> = {};
  const loadVariable = (key: GlobalVariableKey): Promise<void> => {
    if (fields[key] && spreads[key]) return Promise.resolve();
    if (loading[key]) return loading[key]!;
    const promise = (async () => {
      const definition = metadata.variables[key];
      const [meanBuffer, spreadBuffer] = await Promise.all([
        fetchBinary(
          definition.path,
          definition.size_bytes,
          definition.sha256,
        ),
        fetchBinary(
          definition.spread.path,
          definition.spread.size_bytes,
          definition.spread.sha256,
        ),
      ]);
      fields[key] = new Uint16Array(meanBuffer);
      spreads[key] = new Uint16Array(spreadBuffer);
      if (definition.anomaly) {
        const anomalyBuffer = await fetchBinary(
          definition.anomaly.path,
          definition.anomaly.size_bytes,
          definition.anomaly.sha256,
        );
        anomalies[key] = new Uint16Array(anomalyBuffer);
      }
      if (definition.vector) {
        const [uBuffer, vBuffer] = await Promise.all([
          fetchBinary(
            definition.vector.u.path,
            definition.vector.u.size_bytes,
            definition.vector.u.sha256,
          ),
          fetchBinary(
            definition.vector.v.path,
            definition.vector.v.size_bytes,
            definition.vector.v.sha256,
          ),
        ]);
        vectors[key] = {
          u: new Uint16Array(uBuffer),
          v: new Uint16Array(vBuffer),
        };
      }
    })();
    loading[key] = promise;
    return promise;
  };
  const maskDefinition = metadata.grid.ocean_mask;
  const oceanMaskBuffer = await fetchBinary(
    maskDefinition.path,
    maskDefinition.size_bytes,
    maskDefinition.sha256,
  );
  const result: GlobalForecastData = {
    metadata,
    fields,
    anomalies,
    spreads,
    vectors,
    oceanMask: new Uint8Array(oceanMaskBuffer),
    loadVariable,
  };
  await loadVariable("precipitation");
  return result;
}

async function loadData(): Promise<AppData> {
  const requestedIssue = new URLSearchParams(window.location.search).get("issue") ?? "20260728";
  const [
    index,
    forecast,
    globalMetadata,
    validation,
    sources,
    formulas,
    outline,
    world,
    indiaAdmin,
  ] =
    await Promise.all([
    fetchJson<AppData["index"]>("./data/index.json"),
    fetchJson<AppData["forecast"]>(`./data/forecasts/${requestedIssue}.json`),
    fetchJson<GlobalMetadata>("./data/global/metadata.json"),
    fetchJson<AppData["validation"]>("./data/validation.json"),
    fetchJson<AppData["sources"]>("./data/sources.json"),
    fetchJson<AppData["formulas"]>("./data/formulas.json"),
    fetchJson<AppData["outline"]>("./data/india-outline.json"),
    fetchJson<AppData["world"]>("./data/world-countries.geojson"),
    fetchJson<AppData["indiaAdmin"]>("./data/india-admin.json"),
  ]);
  const global = await fetchGlobalData(globalMetadata);
  return {
    index,
    forecast,
    global,
    validation,
    sources,
    formulas,
    outline,
    world,
    indiaAdmin,
  };
}

function shell(): string {
  return `
    <header class="site-header">
      <a class="brand" href="#forecast" aria-label="Atmosphere 42 experimental S2S forecast prototype home">
        <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
        <span><strong>Atmosphere 42</strong><small>Experimental S2S Prototype</small></span>
      </a>
      <nav class="site-nav" aria-label="Primary">
        <a href="#forecast" data-route="forecast">Global</a>
        <a href="#india" data-route="india">India</a>
      </nav>
      <div class="header-status">
        <span class="live-dot" aria-hidden="true"></span>
        <span>28 Jul 2026</span>
      </div>
    </header>
    <main id="content" tabindex="-1"></main>
    <footer class="site-footer">
      <div>
        <strong>Atmosphere 42</strong>
        <span>Experimental S2S forecast prototype · Research use only</span>
      </div>
      <p>42 forecast days · Native 1.5° grid · Natural Earth geography</p>
    </footer>
  `;
}

function renderRoute(data: AppData): void {
  const route = currentRoute();
  routeCleanup?.();
  routeCleanup = undefined;
  const content = document.querySelector<HTMLElement>("#content")!;
  document.body.classList.toggle("global-route", route === "forecast");
  document.body.classList.toggle("india-route", route === "india");
  const statusDate = route === "forecast"
    ? data.global.metadata.issue.initialization
    : data.forecast.issue.initialization;
  const statusLabel = new Intl.DateTimeFormat("en-IN", {
    day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
  }).format(new Date(statusDate));
  document.querySelector<HTMLElement>(".header-status span:last-child")!.textContent = statusLabel;
  document
    .querySelectorAll<HTMLAnchorElement>(".site-nav a")
    .forEach((link) => {
      const active = link.dataset.route === route;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  content.replaceChildren();
  if (route === "forecast") routeCleanup = renderGlobalPage(content, data);
  if (route === "india") renderForecastPage(content, data);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function renderLoadFailure(error: unknown): void {
  const message = error instanceof Error ? error.message : "Unknown data error";
  document.querySelector<HTMLElement>("#content")!.innerHTML = `
    <section class="blocked-state">
      <span class="eyebrow">Data unavailable</span>
      <h1>The forecast package could not be loaded.</h1>
      <p>No partial or broken map has been shown. Check that the compact public data files were built and deployed together.</p>
      <details><summary>Technical detail</summary><code>${message}</code></details>
    </section>
  `;
}

async function start(): Promise<void> {
  const app = document.querySelector<HTMLDivElement>("#app")!;
  app.innerHTML = shell();
  try {
    const data = await loadData();
    renderRoute(data);
    window.addEventListener("hashchange", () => renderRoute(data));
  } catch (error) {
    renderLoadFailure(error);
  }
}

void start();
