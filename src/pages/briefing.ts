import { FEATURED_REPORT } from "../lib/reports";

export function renderBriefingPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="briefing-page">
      <header class="briefing-hero">
        <span class="briefing-eyebrow">S2S Research · Thursday briefing</span>
        <h1>Latest forecast briefing</h1>
        <p>
          The complete India subseasonal outlook for weekly scientific review
          and interpretation.
        </p>
      </header>

      <article class="briefing-feature briefing-report-summary" aria-labelledby="latest-briefing-title">
        <div class="briefing-details">
          <span class="briefing-details__status">Latest briefing</span>
          <h2 id="latest-briefing-title">${FEATURED_REPORT.title}</h2>
          <p>
            Experimental Weeks 1–4 guidance covering rainfall, temperature
            anomalies, and 850 hPa circulation over India.
          </p>

          <dl class="briefing-facts">
            <div><dt>Initialized</dt><dd>${FEATURED_REPORT.date}</dd></div>
            <div><dt>Valid period</dt><dd>${FEATURED_REPORT.validPeriod}</dd></div>
            <div><dt>Forecast range</dt><dd>${FEATURED_REPORT.forecastRange}</dd></div>
            <div><dt>Product</dt><dd>Scientific forecast briefing</dd></div>
          </dl>

          <div class="briefing-actions">
            <a
              class="briefing-action briefing-action--primary"
              href="${FEATURED_REPORT.href}"
              target="_blank"
              rel="noopener noreferrer"
              type="application/pdf"
              aria-label="${FEATURED_REPORT.accessibleLabel}"
            >Read briefing ↗</a>
            <a
              class="briefing-action"
              href="${FEATURED_REPORT.href}"
              download
              type="application/pdf"
            >Download PDF ↓</a>
          </div>
          <small>${FEATURED_REPORT.details}</small>
        </div>
      </article>

      <section class="briefing-report" aria-labelledby="briefing-report-title">
        <header class="briefing-section-heading briefing-section-heading--report">
          <div>
            <span>Full report</span>
            <h2 id="briefing-report-title">Read the complete briefing</h2>
          </div>
          <p>Review the complete ${FEATURED_REPORT.details.split(" · ")[0]} without leaving the dashboard.</p>
        </header>

        <div class="briefing-report__viewer">
          <iframe
            src="${FEATURED_REPORT.href}"
            title="Full ${FEATURED_REPORT.title} for ${FEATURED_REPORT.date}"
            loading="lazy"
            aria-describedby="briefing-report-fallback"
          >
            <p>
              Your browser cannot display embedded PDFs.
              <a
                href="${FEATURED_REPORT.href}"
                target="_blank"
                rel="noopener noreferrer"
                type="application/pdf"
              >Open the full report in a new tab</a>.
            </p>
          </iframe>
        </div>
        <p class="briefing-report__fallback" id="briefing-report-fallback">
          If the embedded report is unavailable,
          <a
            href="${FEATURED_REPORT.href}"
            target="_blank"
            rel="noopener noreferrer"
            type="application/pdf"
          >open the PDF in a new tab</a>
          or
          <a href="${FEATURED_REPORT.href}" download type="application/pdf">download it</a>.
        </p>
      </section>

      <aside class="briefing-context">
        <span>Research context</span>
        <p>
          Briefings and dashboard products are experimental research guidance
          for scientific review, not operational forecasts or warnings.
        </p>
      </aside>
    </section>
  `;
}
