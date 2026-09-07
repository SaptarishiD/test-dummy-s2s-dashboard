import { FEATURED_REPORT } from "../lib/reports";

export function renderBriefingPage(container: HTMLElement): void {
  container.innerHTML = `
    <section class="briefing-page">
      <article class="briefing-feature briefing-report-summary" aria-labelledby="latest-briefing-title">
        <header class="briefing-hero">
          <span class="briefing-eyebrow">Latest Thursday briefing</span>
          <time class="briefing-issue-date">${FEATURED_REPORT.date}</time>
          <h1 id="latest-briefing-title">${FEATURED_REPORT.title}</h1>
        </header>

        <div class="briefing-details">
          <div class="briefing-outlook" role="note" aria-label="Forecast outlook">
            <span>At a glance</span>
            <p>${FEATURED_REPORT.outlook}</p>
          </div>

          <dl class="briefing-facts">
            <div><dt>Valid period</dt><dd>${FEATURED_REPORT.validPeriod}</dd></div>
            <div><dt>Forecast range</dt><dd>${FEATURED_REPORT.forecastRange}</dd></div>
            <div><dt>Document</dt><dd id="briefing-document-details">${FEATURED_REPORT.details}</dd></div>
          </dl>

          <div class="briefing-actions" aria-describedby="briefing-document-details">
            <a
              class="briefing-action briefing-action--primary"
              href="${FEATURED_REPORT.href}"
              target="_blank"
              rel="noopener noreferrer"
              type="application/pdf"
              aria-label="${FEATURED_REPORT.accessibleLabel}; opens in a new tab"
            >Open full briefing <span aria-hidden="true">↗</span></a>
            <a
              class="briefing-action"
              href="${FEATURED_REPORT.href}"
              download
              type="application/pdf"
              aria-label="Download ${FEATURED_REPORT.title} for ${FEATURED_REPORT.date} (${FEATURED_REPORT.details})"
            >Download PDF <span aria-hidden="true">↓</span></a>
          </div>
        </div>
      </article>

      <section class="briefing-report" aria-labelledby="briefing-report-title">
        <header class="briefing-section-heading briefing-section-heading--report">
          <div>
            <span>Full report</span>
            <h2 id="briefing-report-title">Read the briefing</h2>
          </div>
          <p>Embedded PDF preview</p>
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
          Experimental research guidance for scientific review—not an
          operational forecast or warning.
        </p>
      </aside>
    </section>
  `;
}
