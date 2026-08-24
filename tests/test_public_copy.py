"""Focused checks for public contact and release-facing terminology."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_EMAIL = "raj.ayush@students.iiserpune.ac.in"
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_public_copy_contains_only_the_approved_contact_email() -> None:
    public_copy = "\n".join(
        read(path)
        for path in (
            "index.html",
            "src/main.ts",
            "src/pages/archive.ts",
            "src/pages/forecast.ts",
            "src/pages/global.ts",
            "src/pages/outlook.ts",
            "src/pages/team.ts",
            "public/meeting.html",
        )
    )
    assert set(EMAIL_PATTERN.findall(public_copy)) == {PUBLIC_EMAIL}


def test_shared_footer_has_mail_and_institutional_links() -> None:
    shell = read("src/main.ts")
    assert f'href="mailto:{PUBLIC_EMAIL}"' in shell
    assert "https://scdlds.ashoka.edu.in/" in shell
    assert "Wednesday and Saturday" in shell
    assert "Limitations & contact" in shell


def test_dated_global_demo_copy_is_consistent() -> None:
    copy = "\n".join(
        read(path)
        for path in (
            "index.html",
            "README.md",
            "src/pages/global.ts",
        )
    )
    assert "global beta" not in copy.casefold()
    assert "dated global demo" in copy.casefold()
    assert f'href="mailto:{PUBLIC_EMAIL}"' in read("src/pages/global.ts")


def test_navigation_does_not_use_lab_branding() -> None:
    shell = read("src/main.ts")
    assert "S2S Lab" not in shell
    assert 'data-route="models"' not in shell


def test_primary_navigation_is_india_focused() -> None:
    shell = read("src/main.ts")
    assert 'data-route="india"' in shell
    assert 'data-route="archive"' in shell
    assert 'data-route="briefing"' in shell
    assert 'data-route="team"' in shell
    assert 'data-route="forecast"' not in shell
    assert 'data-route="outlook"' not in shell
    assert "?view=global" not in shell


def test_archive_exposes_an_exact_initialization_date_filter() -> None:
    archive = read("src/pages/archive.ts")
    assert 'id="archive-date-filter"' in archive
    assert '<option value="all">All dates</option>' in archive
    assert "issue.initialization === dateFilter.value" in archive
    assert "refreshDateOptions();" in archive


def test_member_count_is_not_promoted_in_the_public_interface() -> None:
    forecast = read("src/pages/forecast.ts")
    archive = read("src/pages/archive.ts")
    briefing = read("src/pages/briefing.ts")
    assert "${forecast.issue.members} members" not in forecast
    assert "member ensemble mean" not in forecast
    assert "Current 100-member proxy" not in forecast
    assert "${issue.members} members" not in archive
    assert "FEATURED_REPORT.ensemble" not in briefing


def test_current_forecast_links_target_the_current_gfs_issue() -> None:
    forecast = read("src/pages/forecast.ts")
    archive = read("src/pages/archive.ts")
    assert 'currentGfsIssue(index)' in forecast
    assert 'href="${currentGfsLink}"' in forecast
    assert 'issueUrl(currentSource, current, activeDomain?.id)' in archive
    assert 'href="${currentHref}"' in archive


def test_featured_report_link_targets_a_valid_public_pdf() -> None:
    shell = read("src/main.ts")
    briefing = read("src/pages/briefing.ts")
    report_metadata = read("src/lib/reports.ts")
    report_path = "reports/s2s-summary-india-2026-08-19.pdf"
    cover_path = "reports/s2s-summary-india-2026-08-19-cover.png"
    report = ROOT / "public" / report_path
    cover = ROOT / "public" / cover_path
    assert f'href: "./{report_path}"' in report_metadata
    assert f'cover: "./{cover_path}"' in report_metadata
    assert 'href="${FEATURED_REPORT.href}"' in briefing
    assert 'src="${FEATURED_REPORT.href}"' in briefing
    assert 'type="application/pdf"' in briefing
    assert 'href="${FEATURED_REPORT.href}" download type="application/pdf"' in briefing
    assert 'aria-describedby="briefing-report-fallback"' in briefing
    assert "19 August 2026 (PDF, 2.1 MB)" in report_metadata
    assert report.read_bytes().startswith(b"%PDF-")
    assert cover.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_team_navigation_lists_scientific_contributors_by_surname() -> None:
    shell = read("src/main.ts")
    team = read("src/pages/team.ts")
    assert 'href="./#briefing" data-route="briefing"' in shell
    assert 'href="./#team" data-route="team"' in shell
    names_by_surname = (
        "Saptarishi Dhanuka",
        "Sandeep Juneja",
        "Parthasarathi Mukhopadhyay",
        "Ayush Raj",
        "Manmeet Singh",
    )
    for name in names_by_surname:
        assert name in team
    assert [team.index(name) for name in names_by_surname] == sorted(
        team.index(name) for name in names_by_surname
    )
    for scientific_role in (
        "Pre-doctoral Fellow · AI weather research",
        "Professor of Computer Science · Centre Director",
        "Visiting Faculty · Earth & Environmental Sciences",
        "MS Thesis Researcher · AI weather research",
        "Project Lead · Assistant Professor",
    ):
        assert scientific_role in team
    assert "publication workflow" not in team.casefold()
    assert "website maintenance" not in team.casefold()


def test_briefing_is_report_only_and_keeps_the_complete_pdf() -> None:
    briefing = read("src/pages/briefing.ts")
    summary_at = briefing.index('class="briefing-feature briefing-report-summary"')
    report_at = briefing.index('class="briefing-report"')
    assert summary_at < report_at
    assert 'class="briefing-team"' not in briefing
    assert "TEAM_MEMBERS" not in briefing
    assert "People behind the forecast" not in briefing
    assert 'class="briefing-report__viewer"' in briefing
    assert 'title="Full ${FEATURED_REPORT.title} for ${FEATURED_REPORT.date}"' in briefing
    assert "Your browser cannot display embedded PDFs." in briefing
    assert "If the embedded report is unavailable," in briefing


def test_team_portraits_are_local_assets() -> None:
    portraits = {
        "ayush-raj.webp": b"RIFF",
        "sandeep-juneja.jpg": b"\xff\xd8\xff",
        "parthasarathi-mukhopadhyay.jpg": b"\xff\xd8\xff",
        "manmeet-singh.jpg": b"\xff\xd8\xff",
        "saptarishi-dhanuka.jpg": b"\xff\xd8\xff",
    }
    team = read("src/pages/team.ts")
    for filename, signature in portraits.items():
        assert f'./team/{filename}' in team
        assert (ROOT / "public" / "team" / filename).read_bytes().startswith(signature)


def test_plan_is_explicitly_a_historical_record() -> None:
    plan = read("PLAN.md")
    assert plan.startswith("# Historical Design Record:")
    assert "It is not the current operations\n> plan or roadmap." in plan
    assert "Historical next milestones (superseded)" in plan
