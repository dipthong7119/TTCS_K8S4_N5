"""Kiểm thử nhanh và fault-injection cho kịch bản reconnect T-46."""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from tests.reconnect_scenario import (
    RunResult,
    _render_comparisons,
    build_plans,
    evaluate_results,
    scenario_exit_code,
)

BACKEND = Path(__file__).resolve().parents[1]


def test_scenario_plans_repeat_for_seed_and_include_both_stop_orders():
    first = build_plans(seed=431, chargers=20, max_disconnects=3)
    second = build_plans(seed=431, chargers=20, max_disconnects=3)

    assert first == second
    assert all(1 <= plan.disconnect_count <= 3 for plan in first)
    assert any(plan.end_offline and plan.available_before_stop for plan in first)
    assert any(plan.end_offline and not plan.available_before_stop for plan in first)


def test_scenario_reports_failure_when_offline_stop_is_ignored(capsys):
    expected = [RunResult(
        code="RC-FAULT",
        transaction_id=7,
        meter_start_wh=10_000,
        meter_stop_wh=12_000,
        expected_kwh=Decimal(2),
        ended_at="2026-10-11T10:00:00Z",
        disconnects=1,
        sample_count=2,
    )]
    # Mô phỏng server bỏ qua StopTransaction bù: phiên vẫn active, chưa có ended_at.
    database_sessions = {"RC-FAULT": [{
        "id": 7,
        "status": "active",
        "meter_start_wh": 10_000,
        "meter_stop_wh": None,
        "energy_kwh": None,
        "ended_at": None,
    }]}

    compared = evaluate_results(expected, database_sessions, {7: 2})

    assert len(compared) == 1
    assert compared[0].ok is False
    assert any("chưa hoàn tất" in error for error in compared[0].errors)
    assert any("kWh=" in error for error in compared[0].errors)
    _render_comparisons(compared)
    assert "LỖI:" in capsys.readouterr().out
    assert scenario_exit_code(compared) != 0


@pytest.mark.scenario
def test_small_live_reconnect_scenario_with_offline_stop_and_no_reboot():
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.reconnect_scenario",
            "--chargers", "5",
            "--max-disconnects", "1",
            "--samples", "4",
            "--tick-seconds", "0.01",
            "--repeats", "1",
            "--seed", "431",
            "--no-boot-on-reconnect",
        ],
        cwd=BACKEND,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "5/5 phiên khớp" in output
