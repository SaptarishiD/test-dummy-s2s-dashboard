import {
  checksumVersionedPath,
  currentGfsIssue,
  issueChecksum,
  issueClass,
  issueInteractiveAvailable,
  issueIsCurrent,
  issuePdfAvailable,
  productsForIssue,
  type CatalogIssue,
  type CatalogSource,
} from "../lib/catalog";
import type { AppData, AvailableProductKey } from "../types";

const PRODUCT_LABELS: Record<AvailableProductKey, string> = {
  rainfall_total: "Rainfall",
  rainfall_anomaly: "Rainfall anomaly",
  temperature_mean: "Temperature",
  temperature_anomaly: "Temperature anomaly",
  wind850_anomaly: "850 hPa wind anomaly",
  regional_probabilities: "Regional probabilities",
  india_pdf: "PDF briefing",
};

function friendlyDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function issueUrl(
  source: CatalogSource,
  issue: CatalogIssue,
  domainId?: string,
): string {
  return `./?source=${source.id}&issue=${issue.id}${domainId && domainId !== "india" ? `&domain=${domainId}` : ""}#india`;
}

export function renderArchivePage(container: HTMLElement, data: AppData): void {
  const { index, domainCatalog, activeDomain } = data;
  if (!index) {
    container.innerHTML = `
      <section class="blocked-state">
        <span class="eyebrow">Archive unavailable</span>
        <h1>The forecast catalogue could not be loaded.</h1>
      </section>
    `;
    return;
  }
  const activeIndex = index;

  const entries = activeIndex.initial_condition_sources
    .flatMap((source) => source.issues.map((issue) => ({ source, issue })))
    .sort((left, right) =>
      right.issue.initialization.localeCompare(left.issue.initialization),
    );
  const years = [...new Set(entries.map(({ issue }) =>
    new Date(issue.initialization).getUTCFullYear(),
  ))].sort((left, right) => right - left);
  const current = currentGfsIssue(activeIndex);

  container.innerHTML = `
    <section class="archive-page">
      <header class="archive-hero">
        <div>
          <span class="archive-eyebrow">Experimental · Validated issue catalogue</span>
          <h1>Forecast archive</h1>
          <p>${activeDomain?.label ?? "India"} · Browse past experimental forecast runs without loading their map data. ERA5 runs are delayed reference experiments; smaller ensembles are kept visibly separate from the current forecast.</p>
        </div>
        ${current ? `
          <a class="archive-current-link" href="./${activeDomain?.id && activeDomain.id !== "india" ? `?domain=${activeDomain.id}` : ""}#india">
            <span>Current forecast</span>
            <strong>${friendlyDate(current.initialization)}</strong>
            <small>GFS proxy · 100 members →</small>
          </a>
        ` : ""}
      </header>

      <section class="archive-policy" aria-label="Archive retention policy">
        <div><strong>12 months</strong><span>Interactive maps and regional files</span></div>
        <div><strong>8 weeks</strong><span>Downloadable PDF briefings</span></div>
        <div><strong>Indefinite</strong><span>Issue metadata and scientific provenance</span></div>
        <p>When a large asset reaches its retention limit, its catalogue record remains visible and is marked metadata-only.</p>
      </section>

      <section class="archive-controls" aria-label="Archive filters">
        ${domainCatalog && domainCatalog.domains.length > 1 ? `<label><span>Domain</span><select id="archive-domain-filter">${domainCatalog.domains.map((domain) => `<option value="${domain.id}" ${domain.id === activeDomain?.id ? "selected" : ""}>${domain.label}</option>`).join("")}</select></label>` : ""}
        <label>
          <span>Source</span>
          <select id="archive-source-filter">
            <option value="all">All sources</option>
            ${activeIndex.initial_condition_sources.map((source) => `<option value="${source.id}">${source.label}</option>`).join("")}
          </select>
        </label>
        <label>
          <span>Year</span>
          <select id="archive-year-filter">
            <option value="all">All years</option>
            ${years.map((year) => `<option value="${year}">${year}</option>`).join("")}
          </select>
        </label>
        <label>
          <span>Ensemble</span>
          <select id="archive-member-filter">
            <option value="all">All ensemble sizes</option>
            <option value="complete">100-member complete</option>
            <option value="limited">Limited experiments</option>
          </select>
        </label>
        <p id="archive-result-count" aria-live="polite"></p>
      </section>

      <div class="archive-list" id="archive-list"></div>
      <div class="archive-empty" id="archive-empty" hidden>
        <strong>No issues match these filters.</strong>
        <p>Choose a different source, year, or ensemble class.</p>
      </div>
    </section>
  `;

  const sourceFilter = container.querySelector<HTMLSelectElement>(
    "#archive-source-filter",
  )!;
  container.querySelector<HTMLSelectElement>("#archive-domain-filter")
    ?.addEventListener("change", (event) => {
      const parameters = new URLSearchParams(window.location.search);
      const domainId = (event.currentTarget as HTMLSelectElement).value;
      if (domainId === domainCatalog?.default_domain) parameters.delete("domain");
      else parameters.set("domain", domainId);
      parameters.delete("source");
      parameters.delete("issue");
      window.location.assign(`./?${parameters.toString()}#archive`);
    });
  const yearFilter = container.querySelector<HTMLSelectElement>(
    "#archive-year-filter",
  )!;
  const memberFilter = container.querySelector<HTMLSelectElement>(
    "#archive-member-filter",
  )!;
  const list = container.querySelector<HTMLElement>("#archive-list")!;
  const empty = container.querySelector<HTMLElement>("#archive-empty")!;
  const resultCount = container.querySelector<HTMLElement>(
    "#archive-result-count",
  )!;

  function render(): void {
    const filtered = entries.filter(({ source, issue }) => {
      const year = String(new Date(issue.initialization).getUTCFullYear());
      return (
        (sourceFilter.value === "all" || source.id === sourceFilter.value) &&
        (yearFilter.value === "all" || year === yearFilter.value) &&
        (memberFilter.value === "all" || issueClass(issue) === memberFilter.value)
      );
    });
    resultCount.textContent = `${filtered.length} issue${filtered.length === 1 ? "" : "s"}`;
    empty.hidden = filtered.length !== 0;
    list.innerHTML = filtered.map(({ source, issue }) => {
      const products = productsForIssue(activeIndex, issue);
      const currentIssue = issueIsCurrent(activeIndex, source, issue);
      const limited = issueClass(issue) === "limited";
      const interactive = issueInteractiveAvailable(issue);
      const pdfPath = issue.pdf;
      const badges = [...products]
        .filter((product) => product !== "india_pdf")
        .map((product) => `<span>${PRODUCT_LABELS[product]}</span>`)
        .join("");
      const presentation = typeof issue.presentation === "object"
        ? issue.presentation.label
        : currentIssue
        ? "Current forecast"
        : limited
          ? "Limited experiment"
          : source.id === "era5"
            ? "Delayed reference"
            : "Archived complete run";
      return `
        <article class="archive-card${currentIssue ? " is-current" : ""}${limited ? " is-limited" : ""}">
          <div class="archive-card__date">
            <span>${source.short_label}</span>
            <time datetime="${issue.initialization}">${friendlyDate(issue.initialization)}</time>
            <small>${
              source.id === "era5"
                ? "Reanalysis · normally 5–7 days delayed"
                : source.id === "ifs"
                ? "Experimental operational initialization"
                : "Operational-input proxy"
            }</small>
          </div>
          <div class="archive-card__summary">
            <span class="archive-card__role">${presentation}</span>
            <strong>${issue.members} members · 42-day guidance</strong>
            <div class="archive-product-list">
              ${badges || "<span>Product metadata only</span>"}
            </div>
          </div>
          <div class="archive-card__actions">
            ${interactive
              ? `<a class="archive-open" href="${issueUrl(source, issue, activeDomain?.id)}">Open maps →</a>`
              : `<span class="archive-expired">Metadata only</span>`}
            ${pdfPath && issuePdfAvailable(issue)
              ? `<a href="${checksumVersionedPath(`./${pdfPath}`, issueChecksum(issue, "pdf"))}" download>PDF briefing ↓</a>`
              : `<small>PDF not retained</small>`}
          </div>
        </article>
      `;
    }).join("");
  }

  [sourceFilter, yearFilter, memberFilter].forEach((filter) => {
    filter.addEventListener("change", render);
  });
  render();
}
