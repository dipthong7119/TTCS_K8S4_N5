"""Pure energy arithmetic shared by session close and reporting logic."""

from decimal import Decimal


def calculate_energy_kwh(meter_start_wh: int, meter_stop_wh: int) -> Decimal | None:
    """Return exact kWh from integer Wh counters; reject a regressing counter."""
    if meter_stop_wh < meter_start_wh:
        return None
    return Decimal(meter_stop_wh - meter_start_wh) / Decimal(1000)
