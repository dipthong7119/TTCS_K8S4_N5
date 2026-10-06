from decimal import Decimal

import pytest

from app.services.session_energy import calculate_energy_kwh


@pytest.mark.parametrize(
    ("meter_start_wh", "meter_stop_wh", "expected_kwh"),
    [
        # Ordinary session: 18.340 kWh to 30.685 kWh = 12.345 kWh.
        (18_340, 30_685, Decimal("12.345")),
        # Regressing meter counters are anomalous; never produce negative energy.
        (27_110, 26_000, None),
        # An unchanged counter is a valid zero-energy session.
        (40_520, 40_520, Decimal("0")),
    ],
)
def test_calculate_energy_kwh(meter_start_wh, meter_stop_wh, expected_kwh):
    assert calculate_energy_kwh(meter_start_wh, meter_stop_wh) == expected_kwh


def test_calculate_energy_kwh_does_not_round_fractional_wh():
    assert calculate_energy_kwh(0, 1) == Decimal("0.001")
