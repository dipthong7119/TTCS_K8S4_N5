"""T-56 verification only: this intentionally corrupt image must never be deployed."""
from pathlib import Path

path = Path('/app/app/ocpp/handlers/boot_notification.py')
source = path.read_text(encoding='utf-8')
needle = '    station = db.query(Station).filter(Station.id == point.station_id).first()'
assert source.count(needle) == 1
fault = '''    from sqlalchemy import text
    db.execute(text("UPDATE charging_sessions SET meter_start_wh = meter_start_wh + 1000 "
                    "WHERE charge_point_code = :code AND ended_at IS NULL"),
               {"code": charge_point_code})
'''
path.write_text(source.replace(needle, fault + needle), encoding='utf-8')
