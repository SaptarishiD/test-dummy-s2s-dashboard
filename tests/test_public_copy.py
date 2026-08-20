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
    assert "Experimental research guidance—not a warning" in shell


def test_experimental_status_and_source_labels_are_unambiguous() -> None:
    shell = read("src/main.ts")
    outlook = read("src/pages/outlook.ts")
    forecast = read("src/pages/forecast.ts")
    archive = read("src/pages/archive.ts")
    global_page = read("src/pages/global.ts")
    assert "Experimental research" in shell
    assert "Experimental archive" in shell
    assert "Experimental demo" in shell
    assert 'candidate.category === "operational_initialization"' in outlook
    assert 'sourceId === "ifs" ? "IFS experimental"' in outlook
    assert "Experimental IFS initialization from operational analysis fields" in forecast
    assert "Experimental operational initialization" in archive
    assert "Experimental · Validated issue catalogue" in archive
    assert "Global forecast <small>demo</small>" in global_page


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


def test_team_page_uses_the_approved_forecast_roster_and_order() -> None:
    team = read("src/pages/team.ts")
    shell = read("index.html")
    expected_order = (
        "Sandeep Juneja",
        "Parthasarathi Mukhopadhyay",
        "Dr. Manmeet Singh",
        "Ayush Raj",
        "Saptarishi Dhanuka",
    )
    positions = [team.index(f'name: "{name}"') for name in expected_order]
    assert positions == sorted(positions)
    assert team.count("scdldsRole:") == 5
    assert 'scdldsRole: "Centre Director"' in team
    assert 'scdldsRole: "Collaborator"' in team
    assert 'scdldsRole: "Project Lead"' in team
    assert 'scdldsRole: "Researcher"' in team
    assert 'scdldsRole: "Pre-doctoral Fellow"' in team
    assert "Bedartha Goswami" not in team
    assert 'name: "Bharat"' not in team
    assert 'class="team-researcher"' not in team
    assert "People behind the forecast." in team
    assert "team-hero__stats" not in team
    assert "team-principles" not in team
    assert 'class="team-page-footer"' in team
    assert "https://scdlds.ashoka.edu.in" in shell.split("img-src", 1)[1].split(";", 1)[0]


def test_public_facing_copy_does_not_use_model_brand_names() -> None:
    public_copy = "\n".join(
        read(path)
        for path in (
            "index.html",
            "src/main.ts",
            "src/pages/archive.ts",
            "src/pages/forecast.ts",
            "src/pages/global.ts",
            "src/pages/outlook.ts",
        )
    )
    assert "FuXi" not in public_copy
    assert "NeuralGCM" not in public_copy

    public_data = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "public/data").rglob("*.json"))
    )
    assert "FuXi" not in public_data
    assert "NeuralGCM" not in public_data


def test_plan_is_explicitly_a_historical_record() -> None:
    plan = read("PLAN.md")
    assert plan.startswith("# Historical Design Record:")
    assert "It is not the current operations\n> plan or roadmap." in plan
    assert "Historical next milestones (superseded)" in plan
