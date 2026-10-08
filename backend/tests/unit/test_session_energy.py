from decimal import Decimal

from app.services.session_energy import calculate_energy_kwh


def test_calculate_energy_kwh(energy_sample_case):
    case = energy_sample_case
    expected = Decimal(case["expected_kwh"]) if case["expected_kwh"] is not None else None
    assert calculate_energy_kwh(case["meter_start_wh"], case["meter_stop_wh"]) == expected


def test_calculate_energy_kwh_does_not_round_fractional_wh():
    assert calculate_energy_kwh(0, 1) == Decimal("0.001")
