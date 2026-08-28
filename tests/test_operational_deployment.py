"""Focused tests for safe catalog validation and static-site publication."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.postdeploy_smoke as postdeploy
from scripts.publish_operational_site import allowed_change
from scripts.publish_operational_site import (
    commit_environment,
    create_disposable_worktree,
    remove_disposable_worktree,
)
from scripts.validate_operational_publication import (
    IssueRef,
    choose_scope,
    issue_records,
    live_inventory,
    public_path,
    source_map,
    validate,
    validate_forecast,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_checked_in_catalog_passes_issue_scoped_live_inventory() -> None:
    index = json.loads((ROOT / "public/data/index.json").read_text(encoding="utf-8"))
    gfs_issue = index["current"]["issue_id"]
    era5_issue = index["latest_reference"]["issue_id"]
    args = SimpleNamespace(
        public_root=ROOT / "public",
        scope="issue",
        source="gfs",
        issue=gfs_issue,
        expected_gfs_issue=gfs_issue,
        expected_era5_issue=era5_issue,
        expected_forecast_sha256=None,
        live_inventory=True,
    )
    receipt = validate(args)
    assert receipt["status"] == "validated"
    assert receipt["issues_validated"] == [f"gfs/{gfs_issue}"]
    assert receipt["catalog_schema"] >= 3


def test_operational_validator_accepts_both_wind_products(tmp_path: Path) -> None:
    source = ROOT / "public/data/forecasts/ifs/20260819.json"
    forecast = json.loads(source.read_text(encoding="utf-8"))
    forecast = copy.deepcopy(forecast)
    forecast["products"]["wind850_mean"] = {
        "label": "Weekly mean 850 hPa wind"
    }
    forecast["issue"]["available_products"] = list(forecast["products"])
    forecast["issue"].setdefault("capabilities", {})["wind850_mean"] = True
    forecast["issue"].pop("initialization_comparison", None)
    forecast["issue"]["downloads"] = {
        "compact_json": "data/forecasts/ifs/20260819.json"
    }
    for week in forecast["weeks"]:
        anomaly = week["vectors"]["wind850_anomaly"]
        u = [value + 6.0 for value in anomaly["u"]]
        v = [value + 3.0 for value in anomaly["v"]]
        week["fields"]["wind850_mean"] = [
            (u_value**2 + v_value**2) ** 0.5
            for u_value, v_value in zip(u, v)
        ]
        week["summary"]["wind850_mean"] = copy.deepcopy(
            week["summary"]["wind850_anomaly"]
        )
        week["vectors"]["wind850_mean"] = {"u": u, "v": v}

    public_root = tmp_path / "public"
    forecast_path = public_root / "data/forecasts/ifs/20260819.json"
    forecast_path.parent.mkdir(parents=True)
    forecast_path.write_text(json.dumps(forecast), encoding="utf-8")
    record = {
        "id": "20260819",
        "initialization": "2026-08-19T00:00:00Z",
        "members": 100,
        "forecast": "forecasts/ifs/20260819.json",
        "available_products": list(forecast["products"]),
        "capabilities": {
            "raw_fields": True,
            "anomalies": True,
            "wind850_mean": True,
            "wind850_anomaly": True,
        },
        "archive": {"pdf_available": False},
    }
    result = validate_forecast(
        public_root,
        live_inventory(public_root),
        {},
        IssueRef("ifs", record),
    )
    assert set(result["weeks"][0]["vectors"]) == {
        "wind850_mean",
        "wind850_anomaly",
    }


def test_current_pointer_cannot_select_limited_ensemble() -> None:
    index = {
        "default_source": "ifs",
        "current": {"source_id": "ifs", "issue_id": "20260801"},
        "latest_reference": {"source_id": "era5", "issue_id": "20260722"},
        "initial_condition_sources": [
            {
                "id": "gfs",
                "default_issue": "20260805",
                "issues": [
                    {
                        "id": "20260805",
                        "initialization": "2026-08-05T00:00:00Z",
                        "members": 100,
                        "forecast": "forecasts/gfs/20260805.json",
                    }
                ],
            },
            {
                "id": "era5",
                "default_issue": "20260722",
                "issues": [
                    {
                        "id": "20260722",
                        "initialization": "2026-07-22T00:00:00Z",
                        "members": 100,
                        "forecast": "forecasts/era5/20260722.json",
                    }
                ],
            },
            {
                "id": "ifs",
                "default_issue": "20260801",
                "issues": [
                    {
                        "id": "20260801",
                        "initialization": "2026-08-01T00:00:00Z",
                        "members": 5,
                        "forecast": "forecasts/ifs/20260801.json",
                    }
                ],
            },
        ],
    }
    sources = source_map(index)
    records = issue_records(sources)
    args = SimpleNamespace(
        scope="current",
        source=None,
        issue=None,
        expected_gfs_issue=None,
        expected_era5_issue=None,
    )
    with pytest.raises(ValueError, match="current issue must be a 100-member"):
        choose_scope(args, index, sources, records)


def test_latest_era5_pointer_accepts_manual_off_cadence_reference() -> None:
    index = {
        "default_source": "ifs",
        "current": {"source_id": "ifs", "issue_id": "20260826"},
        "latest_reference": {"source_id": "era5", "issue_id": "20260820"},
        "initial_condition_sources": [
            {
                "id": "gfs",
                "default_issue": "20260826",
                "issues": [
                    {
                        "id": "20260826",
                        "initialization": "2026-08-26T00:00:00Z",
                        "members": 100,
                        "forecast": "forecasts/gfs/20260826.json",
                    }
                ],
            },
            {
                "id": "era5",
                "default_issue": "20260820",
                "issues": [
                    {
                        "id": "20260820",
                        "initialization": "2026-08-20T00:00:00Z",
                        "members": 100,
                        "forecast": "forecasts/era5/20260820.json",
                    }
                ],
            },
            {
                "id": "ifs",
                "default_issue": "20260826",
                "issues": [
                    {
                        "id": "20260826",
                        "initialization": "2026-08-26T00:00:00Z",
                        "members": 100,
                        "forecast": "forecasts/ifs/20260826.json",
                    }
                ],
            },
        ],
    }
    sources = source_map(index)
    records = issue_records(sources)
    args = SimpleNamespace(
        scope="current",
        source=None,
        issue=None,
        expected_gfs_issue=None,
        expected_era5_issue=None,
    )

    selected, gfs_id, era5_id = choose_scope(args, index, sources, records)

    assert {(ref.source_id, ref.issue_id) for ref in selected} == {
        ("ifs", "20260826"),
        ("gfs", "20260826"),
        ("era5", "20260820"),
    }
    assert gfs_id == "20260826"
    assert era5_id == "20260820"


def test_public_path_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsafe public path"):
        public_path(tmp_path, "../private/config.json")


@pytest.mark.parametrize(
    ("relative", "accepted"),
    [
        ("clean/fuxi-dashboard/public/data/index.json", True),
        ("clean/fuxi-dashboard/public/data/forecasts/gfs/20260805.json", True),
        ("clean/fuxi-dashboard/public/data/forecasts/era5/20260805.json", True),
        ("clean/fuxi-dashboard/public/data/regional/gfs/20260805.json", True),
        ("clean/fuxi-dashboard/public/downloads/gfs/20260805/brief.pdf", True),
        ("clean/fuxi-dashboard/src/main.ts", False),
        ("clean/config/operational/private.json", False),
        ("README.md", False),
    ],
)
def test_publisher_git_allowlist(relative: str, accepted: bool) -> None:
    assert (
        allowed_change(relative, "gfs", "20260805", "clean/fuxi-dashboard")
        is accepted
    )


def test_failed_publication_worktree_cannot_dirty_publishing_clone(
    tmp_path: Path,
) -> None:
    clone = tmp_path / "publisher"
    clone.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=clone, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=clone,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Publication Test"],
        cwd=clone,
        check=True,
    )
    (clone / "tracked.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=clone, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=clone, check=True)
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    worktree = create_disposable_worktree(clone, base_sha)
    (worktree / "unexpected-private-file").write_text("blocked\n", encoding="utf-8")
    remove_disposable_worktree(clone, worktree)
    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=clone,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    assert not worktree.exists()
    assert status == ""


def test_publisher_requires_explicit_institutional_git_identity() -> None:
    with pytest.raises(ValueError, match="required"):
        commit_environment(None, None)
    with pytest.raises(ValueError, match="real institution-owned"):
        commit_environment("S2S Bot", "forecast-ops@institution.example")
    environment = commit_environment("S2S Bot", "forecast-ops@university.edu")
    assert environment["GIT_AUTHOR_NAME"] == "S2S Bot"
    assert environment["GIT_COMMITTER_EMAIL"] == "forecast-ops@university.edu"


def build_smoke_site(root: Path) -> None:
    (root / "data/forecasts/gfs").mkdir(parents=True)
    (root / "data/forecasts/era5").mkdir(parents=True)
    (root / "data/forecasts/ifs").mkdir(parents=True)
    (root / "index.html").write_text('<main id="app"></main>\n', encoding="utf-8")
    index = {
        "default_source": "ifs",
        "current": {"source_id": "ifs", "issue_id": "20260815"},
        "latest_reference": {"source_id": "era5", "issue_id": "20260722"},
        "initial_condition_sources": [],
    }
    for source, issue in (
        ("gfs", "20260805"),
        ("era5", "20260722"),
        ("ifs", "20260815"),
    ):
        forecast_path = f"forecasts/{source}/{issue}.json"
        index["initial_condition_sources"].append(
            {
                "id": source,
                "default_issue": issue,
                "issues": [
                    {
                        "id": issue,
                        "members": 100,
                        "forecast": forecast_path,
                    }
                ],
            }
        )
        forecast = {
            "issue": {
                "initialization": f"{issue[:4]}-{issue[4:6]}-{issue[6:]}T00:00:00Z",
                "members": 100,
                "initial_condition_source": {"id": source},
            }
        }
        (root / "data" / forecast_path).write_text(
            json.dumps(forecast), encoding="utf-8"
        )
    (root / "data/index.json").write_text(json.dumps(index), encoding="utf-8")
    entries = []
    for path in sorted((root / "data").rglob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": len(payload),
                "sha256": digest(payload),
            }
        )
    manifest = {
        "schema_version": 1,
        "deployed_commit": "abc123",
        "files": entries,
    }
    (root / "data/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_postdeploy_smoke_verifies_commit_pointers_and_forecasts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_smoke_site(tmp_path)
    monkeypatch.setattr(
        postdeploy,
        "fetch",
        lambda _base, relative, _attempts, _timeout: (tmp_path / relative).read_bytes(),
    )
    args = SimpleNamespace(
        base_url="https://example.invalid/s2s/",
        expected_commit="abc123",
        expected_index=tmp_path / "data/index.json",
        expected_gfs_issue=None,
        expected_era5_issue=None,
        attempts=1,
        timeout=2.0,
    )
    receipt = postdeploy.smoke(args)
    assert receipt["status"] == "healthy"
    assert receipt["default_source"] == "ifs"
    assert receipt["current_source"] == "ifs"
    assert receipt["current_issue"] == "20260815"
    assert receipt["current_gfs_issue"] == "20260805"
    assert receipt["latest_era5_issue"] == "20260722"
    assert len(receipt["verified_assets"]) == 3


def test_postdeploy_smoke_rejects_a_non_ifs_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_smoke_site(tmp_path)
    index_path = tmp_path / "data/index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["default_source"] = "gfs"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(
        postdeploy,
        "fetch",
        lambda _base, relative, _attempts, _timeout: (tmp_path / relative).read_bytes(),
    )
    args = SimpleNamespace(
        base_url="https://example.invalid/s2s/",
        expected_commit=None,
        expected_index=None,
        expected_gfs_issue=None,
        expected_era5_issue=None,
        attempts=1,
        timeout=2.0,
    )
    with pytest.raises(ValueError, match="deployed default source is not IFS"):
        postdeploy.smoke(args)


def test_postdeploy_smoke_verifies_selected_ifs_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_smoke_site(tmp_path)
    monkeypatch.setattr(
        postdeploy,
        "fetch",
        lambda _base, relative, _attempts, _timeout: (tmp_path / relative).read_bytes(),
    )
    args = SimpleNamespace(
        base_url="https://example.invalid/s2s/",
        expected_commit="abc123",
        expected_index=tmp_path / "data/index.json",
        expected_gfs_issue=None,
        expected_era5_issue=None,
        expected_source="ifs",
        expected_issue="20260815",
        attempts=1,
        timeout=2.0,
    )
    receipt = postdeploy.smoke(args)
    assert "data/forecasts/ifs/20260815.json" in receipt["verified_assets"]


def test_postdeploy_fetch_rejects_non_http_origin() -> None:
    with pytest.raises(ValueError, match="must be HTTP"):
        postdeploy.fetch("file:///tmp/site", "data/index.json", 1, 1.0)


def test_postdeploy_retries_whole_snapshot_during_cdn_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def eventually_healthy(_args: SimpleNamespace) -> dict[str, str]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("old catalog still cached")
        return {"status": "healthy"}

    monkeypatch.setattr(postdeploy, "smoke_once", eventually_healthy)
    monkeypatch.setattr(postdeploy.time, "sleep", lambda _seconds: None)
    receipt = postdeploy.smoke(SimpleNamespace(attempts=3))
    assert receipt == {"status": "healthy"}
    assert calls == 3


def test_root_workflow_template_runs_all_release_gates() -> None:
    workflow = (ROOT / "deployment/github/deploy-pages.yml").read_text(
        encoding="utf-8"
    )
    assert "working-directory: clean/fuxi-dashboard" not in workflow
    assert "cache-dependency-path: package-lock.json" in workflow
    assert "validate_operational_publication.py --scope all" in workflow
    assert "validate_global_web_data.py" in workflow
    assert "npm run build" in workflow
    assert "postdeploy_smoke.py" in workflow
    assert "--expected-commit" in workflow
