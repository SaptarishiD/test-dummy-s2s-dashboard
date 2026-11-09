import "./styles/main.css";
import "./styles/operational.css";
import "./styles/probabilistic.css";
import type {
  AppData,
  ForecastData,
  ForecastDomainCatalog,
  IndiaMapGeographyData,
  InitializationComparisonData,
  InitialConditionSourceId,
  IssueIndexData,
  ValidationData,
} from "./types";
import {
  checksumVersionedPath,
  currentForecast,
  findIssue,
  issueChecksum,
} from "./lib/catalog";
import { FEATURED_REPORT } from "./lib/reports";

type Route = "india" | "archive" | "briefing" | "team";

const ROUTES = new Set<Route>([
  "india",
  "archive",
  "briefing",
  "team",
]);
const ROUTE_FOCUS_STORAGE_KEY = "fuxi-dashboard-focus-content";

function storedRouteFocus(): boolean {
  try {
    return window.sessionStorage.getItem(ROUTE_FOCUS_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function rememberRouteFocus(): void {
  try {
    window.sessionStorage.setItem(ROUTE_FOCUS_STORAGE_KEY, "true");
  } catch {
    // Focus transfer still works for same-document navigation.
  }
}

function clearStoredRouteFocus(): void {
  try {
    window.sessionStorage.removeItem(ROUTE_FOCUS_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in privacy-restricted contexts.
  }
}

function currentRoute(): Route {
  const hash = window.location.hash.replace("#", "") as Route;
  return ROUTES.has(hash) ? hash : "india";
}

async function fetchJson<T>(path: string, cache?: RequestCache): Promise<T> {
  const response = await fetch(path, cache ? { cache } : undefined);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function loadData(): Promise<AppData> {
  const route = currentRoute();
  const domainCatalog = await fetchJson<ForecastDomainCatalog>(
    "./data/domains.json",
    "no-store",
  );
  const parameters = new URLSearchParams(window.location.search);
  const activeDomain = domainCatalog.domains.find(
    (domain) => domain.id === parameters.get("domain"),
  ) ?? domainCatalog.domains.find(
    (domain) => domain.id === domainCatalog.default_domain,
  );
  if (!activeDomain) throw new Error("No forecast domain is configured");

  if (route === "briefing" || route === "team") {
    return { domainCatalog, activeDomain };
  }

  if (route === "archive") {
    return {
      index: await fetchJson<IssueIndexData>(
        `./data/${activeDomain.catalog}`,
        "no-store",
      ),
      domainCatalog,
      activeDomain,
    };
  }

  const index = await fetchJson<IssueIndexData>(
    `./data/${activeDomain.catalog}`,
    "no-store",
  );
  const selection = findIssue(
    index,
    parameters.get("source"),
    parameters.get("issue"),
  );
  if (!selection) throw new Error("No forecast issue is available");
  const { source, issue } = selection;
  const [forecast, validation, indiaGeography] = await Promise.all([
    fetchJson<ForecastData>(checksumVersionedPath(
      `./data/${issue.forecast}`,
      issueChecksum(issue, "forecast"),
    )),
    fetchJson<ValidationData>(checksumVersionedPath(
      issue.validation ? `./data/${issue.validation}` : "./data/validation.json",
      issueChecksum(issue, "validation"),
    ), issue.validation ? undefined : "no-store"),
    fetchJson<IndiaMapGeographyData>(
      `./data/${activeDomain.geography}`,
      "no-store",
    ),
  ]);
  if (forecast.issue.initial_condition_source.id !== source.id) {
    throw new Error("Forecast source does not match the selected initialization source");
  }
  const comparisonPath = forecast.issue.initialization_comparison?.comparison;
  const comparedSourceIds =
    forecast.issue.initialization_comparison?.compared_source_ids;
  let initializationComparison: InitializationComparisonData | undefined;
  let comparisonForecasts:
    | Partial<Record<InitialConditionSourceId, ForecastData>>
    | undefined;
  if (
    activeDomain.id === "india" &&
    comparisonPath &&
    comparedSourceIds && comparedSourceIds.length >= 2
  ) {
    initializationComparison = await fetchJson<InitializationComparisonData>(
      `./data/${comparisonPath}`,
    );
    const entries = await Promise.all(
      Object.entries(initializationComparison.sources).map(async ([sourceId, record]) => [
        sourceId as InitialConditionSourceId,
        await fetchJson<ForecastData>(`./data/${record.public_forecast}`),
      ] as const),
    );
    comparisonForecasts = Object.fromEntries(entries) as Partial<
      Record<InitialConditionSourceId, ForecastData>
    >;
  }
  return {
    index,
    forecast,
    validation,
    indiaGeography,
    initializationComparison,
    comparisonForecasts,
    domainCatalog,
    activeDomain,
  };
}

function shell(): string {
  return `
    <header class="site-header">
      <div class="site-header__inner">
        <a
          class="institution-brand"
          href="./#india"
          aria-label="Go to the latest India forecast — Safexpress Centre for Data, Learning and Decision Sciences, Ashoka University"
        >
          <span class="institution-brand__marks" aria-hidden="true">
            <img
              class="institution-brand__ashoka"
              src="./brand/ashoka-university.png"
              alt=""
            />
            <img
              class="institution-brand__centre"
              src="./brand/scdlds-centre.png"
              alt=""
            />
          </span>
          <span class="institution-brand__service" aria-hidden="true">
            <strong>S2S Forecast</strong>
            <small>Research dashboard</small>
          </span>
        </a>
        <nav class="site-nav" aria-label="Primary navigation">
          <a href="./#india" data-route="india">
            <strong>Forecast</strong>
            <small>Latest maps</small>
          </a>
          <a href="./#briefing" data-route="briefing">
            <strong>Briefing</strong>
            <small>Weekly analysis</small>
          </a>
          <a href="./#archive" data-route="archive">
            <strong>Archive</strong>
            <small>Past issues</small>
          </a>
          <a href="./#team" data-route="team">
            <strong>Team</strong>
            <small>People &amp; methods</small>
          </a>
        </nav>
        <div class="header-utility">
          <div class="header-status" role="status" aria-live="polite">
            <span class="live-dot" aria-hidden="true"></span>
            <span class="header-status__label">Loading latest issue</span>
          </div>
        </div>
      </div>
    </header>
    <main id="content" tabindex="-1"></main>
    <footer class="site-footer" aria-label="About this forecast service">
      <div class="site-footer__brand">
        <strong>S2S Research</strong>
        <span>Safexpress Centre for Data, Learning and Decision Sciences · Ashoka University</span>
        <p>Experimental research guidance · Not an operational forecast, warning, or decision trigger.</p>
      </div>
      <div class="site-footer__section" id="about">
        <strong>About & methods</strong>
        <p>AI Ensemble Model output is summarized as weekly India fields. Anomalies appear only when a seasonally matched model climatology is available.</p>
      </div>
      <div class="site-footer__section" id="schedule">
        <strong>Update schedule</strong>
        <p>Main guidance is targeted every Wednesday and Sunday after source-data checks. GFS is retained as a secondary proxy, and ERA5 is a delayed reference.</p>
      </div>
      <div class="site-footer__section" id="limitations">
        <strong>Limitations & contact</strong>
        <p>Long leads describe broad ensemble tendencies, not local weather. Public contact: <a href="mailto:s2s.scdlds@ashoka.edu.in">s2s.scdlds@ashoka.edu.in</a> · <a href="https://scdlds.ashoka.edu.in/" target="_blank" rel="noreferrer">Centre website ↗</a></p>
      </div>
    </footer>
  `;
}

let routeCleanup: (() => void) | undefined;
let focusContentAfterRoute = storedRouteFocus();
let hasRenderedRoute = false;

async function renderRoute(data: AppData): Promise<void> {
  const route = currentRoute();
  if (route === "india" && !data.forecast) {
    window.location.assign("./#india");
    return;
  }
  const content = document.querySelector<HTMLElement>("#content")!;
  document.body.classList.toggle("india-route", route === "india");
  document.body.classList.toggle("archive-route", route === "archive");
  document.body.classList.toggle("briefing-route", route === "briefing");
  document.body.classList.toggle("team-route", route === "team");
  const statusDate = data.forecast?.issue.initialization ??
    (data.index ? currentForecast(data.index)?.issue.initialization : undefined);
  const formattedStatusDate = statusDate
    ? new Intl.DateTimeFormat("en-IN", {
      day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
    }).format(new Date(statusDate))
    : undefined;
  const statusLabel = route === "briefing"
    ? `Latest briefing · ${FEATURED_REPORT.date}`
    : route === "team"
      ? ""
      : route === "archive"
        ? formattedStatusDate
          ? `Catalogue through · ${formattedStatusDate}`
          : "Validated issue catalogue"
        : formattedStatusDate
          ? `Latest run · ${formattedStatusDate}`
          : "Loading latest issue";
  const headerUtility = document.querySelector<HTMLElement>(".header-utility")!;
  const headerStatus = document.querySelector<HTMLElement>(".header-status")!;
  headerUtility.hidden = route === "team";
  headerStatus.dataset.state = route === "india" || route === "archive"
    ? "validated"
    : "context";
  document.querySelector<HTMLElement>(".header-status__label")!.textContent = statusLabel;
  document
    .querySelectorAll<HTMLAnchorElement>(".site-nav a")
    .forEach((link) => {
      const active = link.dataset.route === route;
      link.classList.toggle("is-active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  routeCleanup?.();
  routeCleanup = undefined;
  content.replaceChildren();
  if (route === "india") {
    const { renderForecastPage } = await import("./pages/forecast");
    routeCleanup = renderForecastPage(content, data);
  }
  if (route === "archive") {
    const { renderArchivePage } = await import("./pages/archive");
    renderArchivePage(content, data);
  }
  if (route === "briefing") {
    const { renderBriefingPage } = await import("./pages/briefing");
    renderBriefingPage(content);
  }
  if (route === "team") {
    const { renderTeamPage } = await import("./pages/team");
    renderTeamPage(content);
  }
  if (hasRenderedRoute || focusContentAfterRoute) {
    content.focus({ preventScroll: true });
  }
  hasRenderedRoute = true;
  focusContentAfterRoute = false;
  clearStoredRouteFocus();
  window.scrollTo(0, 0);
  window.requestAnimationFrame(() => window.scrollTo(0, 0));
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
  const content = document.querySelector<HTMLElement>("#content")!;
  document.querySelector<HTMLAnchorElement>(".skip-link")
    ?.addEventListener("click", (event) => {
      event.preventDefault();
      content.focus({ preventScroll: true });
      content.scrollIntoView({ block: "start" });
    });
  app.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const link = target.closest<HTMLAnchorElement>("a");
    const route = link?.hash.replace("#", "") as Route | undefined;
    if (route && ROUTES.has(route) && link?.href !== window.location.href) {
      focusContentAfterRoute = true;
      rememberRouteFocus();
    }
  });
  try {
    const data = await loadData();
    await renderRoute(data);
    window.addEventListener("hashchange", () => {
      if (currentRoute() === "india" && !data.forecast) {
        rememberRouteFocus();
        window.location.reload();
        return;
      }
      if (currentRoute() === "archive" && !data.index) {
        rememberRouteFocus();
        window.location.reload();
        return;
      }
      void renderRoute(data).catch(renderLoadFailure);
    });
  } catch (error) {
    renderLoadFailure(error);
  }
}

void start();
