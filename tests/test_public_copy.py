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


def test_team_page_marks_centre_affiliations_without_mislabeling_bedartha() -> None:
    team = read("src/pages/team.ts")
    shell = read("index.html")
    expected_order = (
        "Sandeep Juneja",
        "Parthasarathi Mukhopadhyay",
        "Dr. Manmeet Singh",
        "Bedartha Goswami",
        "Saptarishi Dhanuka",
        "Bharat",
    )
    positions = [team.index(f'name: "{name}"') for name in expected_order]
    assert positions == sorted(positions)
    assert team.count("scdldsRole:") == 5
    assert 'scdldsRole: "Centre Director"' in team
    assert 'scdldsRole: "Collaborator"' in team
    assert 'scdldsRole: "Academic visitor"' in team
    assert 'scdldsRole: "Pre-doctoral Fellow"' in team
    assert 'scdldsRole: "Summer Intern"' in team
    bedartha = team.split('name: "Bedartha Goswami"', 1)[1].split("  },", 1)[0]
    assert "scdldsRole" not in bedartha
    assert "SCDLDS · Researcher" in team
    assert "Project manager" not in team
    assert 'class="team-researcher"' in team
    assert "Research group." in team
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
