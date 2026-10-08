"""T-56 / SCRUM-185: isolated, reproducible 20-charger CI acceptance runner."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.kwh_reconciliation import (
    calculate_session_kwh,
    export_markdown_table,
    reconcile_datasets,
)

TEST_NAME = "test_scrum182_20_chargers_random_disconnect_kwh_integrity"
TEST_TARGET = f"tests/test_scrum182_20charger_scenario.py::{TEST_NAME}"


def reconciliation_report(raw: dict, expected_count: int = 20) -> dict:
    """Adapt real SCRUM-182 output to the SCRUM-183/184 report contract."""
    items = raw["items"]
    if raw["charger_count"] != expected_count or len(items) != expected_count:
        raise ValueError(f"Expected {expected_count} chargers/sessions, got {raw['charger_count']}/{len(items)}")
    if raw["disconnect_count"] != expected_count or any(not item["do_disconnect"] for item in items):
        raise ValueError("Every charge point must reconnect during the CI acceptance scenario")
    codes = [item["code"] for item in items]
    ids = [item["transaction_id"] for item in items if item["transaction_id"] is not None]
    if len(set(codes)) != len(codes) or len(set(ids)) != len(ids):
        raise ValueError(f"Duplicate charge points or transaction IDs: codes={codes}, sessions={ids}")
    systems, simulators = [], []
    faults = {}
    for index, item in enumerate(items):
        session_id = item["transaction_id"] or f"missing-{index}"
        expected = calculate_session_kwh(item["meter_start_wh"], item["meter_stop_wh"] or item["meter_start_wh"])
        actual = float(item["db_kwh"])
        if expected is None or not math.isfinite(actual):
            raise ValueError(f"Invalid kWh: charge_point={item['code']} session={session_id}")
        simulators.append({
            "session_id": session_id, "charge_point_code": item["code"], "connector_id": 1,
            "meter_start_wh": item["meter_start_wh"], "meter_stop_wh": item["meter_stop_wh"],
            "simulator_kwh": expected, "disconnect_count": item["disconnect_count"],
        })
        if item["db_status"] is not None:
            systems.append({**simulators[-1], "system_kwh": actual})
        errors = list(item.get("errors", []))
        if item["db_status"] != "completed" or not item["kwh_ok"] or expected <= 0:
            errors.append(f"status={item['db_status']}, integrity_ok={item['kwh_ok']}")
        if item["do_disconnect"] and not 1 <= item["disconnect_count"] <= 3:
            errors.append(f"invalid reconnect count={item['disconnect_count']}")
        if errors:
            faults[str(session_id)] = "; ".join(errors)
    report = reconcile_datasets(systems, simulators, tolerance=0.001)
    for session in report["sessions"]:
        fault = faults.get(str(session["session_id"]))
        if fault:
            if session["status"] == "MATCH":
                session["status"] = "MISMATCH"
            session["notes"] = fault
    summary = report["summary"]
    matched = sum(session["status"] == "MATCH" for session in report["sessions"])
    passed = matched == expected_count and raw["summary"]["all_passed"] is True
    summary.update(matched_sessions=matched, mismatched_sessions=expected_count - matched,
                   match_percentage=round(100 * matched / expected_count, 2), verdict="PASSED" if passed else "FAILED")
    report["metadata"] = {"title": "CI: real 20-charger kWh reconciliation", "task": "T-56 / SCRUM-185",
                          "generated_at": raw["generated_at"], "total_charge_points": expected_count,
                          "tolerance_kwh": 0.001, "random_seed": raw["random_seed"], "data_source": "Docker/PostgreSQL"}
    return report


def validate_junit(path: Path) -> None:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    if len(cases) != 1 or cases[0].get("name") != TEST_NAME:
        raise ValueError("The required 20-charger test did not execute exactly once")
    if any(cases[0].find(tag) is not None for tag in ("skipped", "failure", "error")):
        raise ValueError("The required 20-charger test failed, errored or was skipped")


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()
    deadline = started + args.timeout_seconds
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = args.output_dir.resolve() / run_id
    output.mkdir(parents=True)
    project = args.project or f"csms-sprint3-{uuid.uuid4().hex[:8]}"
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise ValueError("Compose project must contain lowercase letters, digits, underscores or hyphens")
    environment = os.environ | {"CSMS_IMAGE": args.image, "CSMS_SIMULATOR_IMAGE": args.image,
                                "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    compose = ["docker", "compose", "--env-file", str(ROOT / ".env.example"), "-p", project,
               "-f", str(ROOT / "docker-compose.acceptance.yml")]
    manifest = {"task": "T-56 / SCRUM-185", "project": project, "image": args.image,
                "charger_count": 20, "repeat": args.repeat, "runs": [], "verdict": "FAILED"}
    owns_stack = False

    def command(arguments: list[str], log: str, *, env=None, check=True, cleanup=False):
        timeout = 30 if cleanup else max(1, deadline - time.monotonic())
        with (output / log).open("w", encoding="utf-8") as stream:
            result = subprocess.run(arguments, cwd=ROOT, env=env or environment, stdout=stream,
                                    stderr=subprocess.STDOUT, text=True, timeout=timeout, check=False)
        contents = (output / log).read_text(encoding="utf-8", errors="replace")
        if not cleanup:
            print(contents, end="", flush=True)
        if check and result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(arguments)}; log={output / log}")
        return result.returncode, contents

    try:
        _, existing = command(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}"], "preflight.log")
        if existing.strip():
            raise RuntimeError(f"Refusing to modify existing Compose project {project}; choose a different --project")
        owns_stack = True
        if not args.no_build:
            command(compose + ["build", "app"], "docker-build.log")
        # Pull only when unavailable locally; retry registry transport failures, never tests.
        image_available, _ = command(["docker", "image", "inspect", "postgres:15-alpine", "--format", "{{.Id}}"], "postgres-image.log", check=False)
        if image_available:
            for attempt in range(1, 4):
                exit_code, _ = command(compose + ["pull", "db"], f"postgres-pull-{attempt}.log", check=False)
                if exit_code == 0:
                    break
                if attempt == 3:
                    raise RuntimeError("PostgreSQL image could not be downloaded after 3 attempts")
                time.sleep(min(5, max(0, deadline - time.monotonic())))
        command(compose + ["up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "90", "db", "app"], "docker-up.log")
        _, image_id = command(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], "app-image.log")
        manifest["image_id"] = image_id.strip()
        manifest["git_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        markdown = ["# T-56 / SCRUM-185 — CI acceptance", f"Commit: `{manifest['git_sha']}`", ""]
        for number in range(1, args.repeat + 1):
            folder = output / f"run-{number}"
            folder.mkdir()
            scenario = folder / "scenario.json"
            junit = folder / "junit.xml"
            seed = args.seed + number - 1
            test_env = environment | {
                "SCRUM182_CHARGER_COUNT": "20", "SCRUM182_DISCONNECT_COUNT": "20",
                "SCRUM182_DISCONNECT_MIN": "1", "SCRUM182_DISCONNECT_MAX": "3",
                "SCRUM182_METER_READINGS": "4", "SCRUM182_METER_STEP_WH": "2500",
                "SCRUM182_RANDOM_SEED": str(seed), "SCRUM182_RESULT_PATH": str(scenario),
                "SCRUM182_SESSION_CLOSE_TIMEOUT": "15",
            }
            print(f"[T-56] Run {number}/{args.repeat}; 20 chargers, 1-3 reconnects each, seed={seed}", flush=True)
            exit_code, _ = command([sys.executable, "-m", "pytest", TEST_TARGET, "--docker-project", project,
                                   "-v", "-s", "--tb=short", f"--junitxml={junit}"], f"run-{number}/pytest.log", env=test_env, check=False)
            if scenario.exists():
                raw = json.loads(scenario.read_text(encoding="utf-8"))
                if raw["random_seed"] != seed:
                    raise RuntimeError(f"Run {number}: expected seed {seed}, got {raw['random_seed']}")
                report = reconciliation_report(raw)
                (folder / "reconciliation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                table = export_markdown_table(report)
                (folder / "reconciliation.md").write_text(table, encoding="utf-8")
                markdown += [f"## Run {number} (seed {seed})", table, ""]
                (output / "summary.md").write_text("\n".join(markdown), encoding="utf-8")
                manifest["runs"].append({"run": number, "seed": seed, **report["summary"]})
            else:
                raise RuntimeError(f"Run {number}: no scenario report was produced; inspect pytest.log and junit.xml")
            if exit_code or report["summary"]["verdict"] != "PASSED":
                raise RuntimeError(f"Run {number} failed: {report['summary']}; see {folder}")
            validate_junit(junit)
        manifest["verdict"] = "PASSED"
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.SubprocessError) as exc:
        manifest["error"] = str(exc)
        print(f"[T-56] FAILED: {exc}", flush=True)
    finally:
        if owns_stack:
            try:
                command(compose + ["ps", "--all"], "docker-ps.log", cleanup=True)
                command(compose + ["logs", "--no-color", "--tail", "200"], "docker.log", cleanup=True)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                manifest["diagnostic_error"] = str(exc)
            try:
                command(compose + ["down", "-v", "--remove-orphans"], "docker-cleanup.log", cleanup=True)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                manifest.update(verdict="FAILED", cleanup_error=str(exc))
        manifest["elapsed_seconds"] = round(time.monotonic() - started, 2)
        if manifest["elapsed_seconds"] >= 300:
            manifest.update(verdict="FAILED", error="Acceptance exceeded the 5-minute limit")
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_file = output / "summary.md"
        if os.getenv("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
                stream.write(summary_file.read_text(encoding="utf-8") if summary_file.exists() else f"## T-56: FAILED\n\n{manifest.get('error', '')}\n")
                stream.write(f"\n\nVerdict: **{manifest['verdict']}**. Runtime: {manifest['elapsed_seconds']}s.\n")
        print(f"[T-56] {manifest['verdict']} in {manifest['elapsed_seconds']}s; reports={output}", flush=True)
    return 0 if manifest["verdict"] == "PASSED" else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=os.getenv("CSMS_IMAGE", "csms-app:sprint3-ci"))
    parser.add_argument("--no-build", action="store_true", help="Use the image already built by CI")
    parser.add_argument("--project", help="Unused isolated Compose project; generated by default")
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout-seconds", type=int, choices=range(30, 241), default=240)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "sprint3-ci")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
