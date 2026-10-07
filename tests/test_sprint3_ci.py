"""T-56 / SCRUM-185: fail closed and preserve evidence for CI acceptance."""

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_sprint3_ci as runner


def scenario():
    return {
        "charger_count": 20, "disconnect_count": 20, "random_seed": 42,
        "generated_at": "2026-10-07T00:00:00Z", "summary": {"all_passed": True},
        "items": [{"code": f"SCRUM182-SIM-{number:02d}", "transaction_id": number,
                   "meter_start_wh": 500, "meter_stop_wh": 10500, "expected_kwh": 10.0,
                   "db_kwh": 10.0, "db_status": "completed", "do_disconnect": True,
                   "disconnect_count": 1 + number % 3, "kwh_ok": True, "errors": []}
                  for number in range(1, 21)],
    }


def test_real_report_uses_scrum183_contract():
    report = runner.reconciliation_report(scenario())
    assert report["summary"]["verdict"] == "PASSED"
    assert report["summary"]["matched_sessions"] == 20
    assert report["summary"]["total_simulator_kwh"] == report["summary"]["total_system_kwh"] == 200
    assert report["sessions"][0]["session_id"] == 1
    assert report["sessions"][0]["disconnect_count"] == 2
    assert report["metadata"]["data_source"] == "Docker/PostgreSQL"


@pytest.mark.parametrize("fault", ["kwh", "lost_meter_values", "open_session", "missing_session", "no_reconnect"])
def test_report_rejects_recovery_failures_even_if_raw_summary_claims_pass(fault):
    raw = scenario()
    item = raw["items"][3]
    if fault == "kwh":
        item["db_kwh"] = 7.5
    elif fault == "lost_meter_values":
        item["errors"] = ["MeterValues lost after reconnect"]
    elif fault == "open_session":
        item["db_status"] = "active"
    elif fault == "missing_session":
        item["db_status"] = None
        item["transaction_id"] = None
    else:
        item["disconnect_count"] = 0
    report = runner.reconciliation_report(raw)
    assert report["summary"]["verdict"] == "FAILED"
    assert report["summary"]["matched_sessions"] == 19
    assert report["summary"]["mismatched_sessions"] == 1
    failed = next(row for row in report["sessions"] if row["charge_point_code"] == item["code"])
    assert failed["status"] != "MATCH"


@pytest.mark.parametrize("fault", ["empty", "too_few", "duplicate_code", "duplicate_session", "nan", "disconnected_subset"])
def test_malformed_or_reduced_scenario_cannot_satisfy_gate(fault):
    raw = scenario()
    if fault == "empty":
        raw["items"] = []
    elif fault == "too_few":
        raw["items"].pop()
    elif fault == "duplicate_code":
        raw["items"][1]["code"] = raw["items"][0]["code"]
    elif fault == "duplicate_session":
        raw["items"][1]["transaction_id"] = raw["items"][0]["transaction_id"]
    elif fault == "nan":
        raw["items"][0]["db_kwh"] = float("nan")
    else:
        raw["disconnect_count"] = 5
    with pytest.raises(ValueError):
        runner.reconciliation_report(raw)


@pytest.mark.parametrize("contents", ["<testsuite/>", '<testsuite><testcase name="other"/></testsuite>',
                                      f'<testsuite><testcase name="{runner.TEST_NAME}"><skipped/></testcase></testsuite>'])
def test_empty_or_skipped_pytest_run_is_not_green(tmp_path, contents):
    path = tmp_path / "junit.xml"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        runner.validate_junit(path)


@pytest.mark.parametrize("failure", [None, "pytest", "cleanup", "existing_project"])
def test_runner_propagates_failure_preserves_reports_and_cleans_only_owned_stack(tmp_path, monkeypatch, failure):
    commands = []
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "a" * 40)

    def fake_run(arguments, **kwargs):
        commands.append(arguments)
        exit_code = 0
        if arguments[:3] == ["docker", "ps", "-aq"] and failure == "existing_project":
            kwargs["stdout"].write("existing-container\n")
        elif "pytest" in arguments:
            environment = kwargs["env"]
            Path(environment["SCRUM182_RESULT_PATH"]).write_text(json.dumps(copy.deepcopy(scenario())), encoding="utf-8")
            junit = Path(next(arg.split("=", 1)[1] for arg in arguments if arg.startswith("--junitxml=")))
            junit.write_text(f'<testsuite><testcase name="{runner.TEST_NAME}"/></testsuite>', encoding="utf-8")
            if failure == "pytest":
                exit_code = 1
        elif "down" in arguments and failure == "cleanup":
            exit_code = 1
        return subprocess.CompletedProcess(arguments, exit_code)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    args = argparse.Namespace(output_dir=tmp_path / "reports", project="csms-test", image="csms-app:test",
                              no_build=True, repeat=1, seed=42, timeout_seconds=240)
    result = runner.run(args)
    manifest_path = next(args.output_dir.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert result == (0 if failure is None else 1)
    assert manifest["verdict"] == ("PASSED" if failure is None else "FAILED")
    if failure == "existing_project":
        assert not any("up" in command or "down" in command for command in commands)
    else:
        assert any("down" in command for command in commands)
        assert (manifest_path.parent / "run-1/reconciliation.json").exists()
        assert (manifest_path.parent / "run-1/reconciliation.md").exists()
        assert (manifest_path.parent / "run-1/junit.xml").exists()
