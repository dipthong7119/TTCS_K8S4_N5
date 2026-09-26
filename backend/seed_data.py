import os
import sys

# Add backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.station import Station
from app.models.charge_point import ChargePoint, Connector
from app.models.user import User
from datetime import datetime

def seed_data():
    db: Session = SessionLocal()
    
    # Check if we already have stations
    if db.query(Station).count() > 0:
        print("Data already seeded.")
        return

    # Assuming user 2 is owner@csms.local
    owner = db.query(User).filter(User.email == "owner@csms.local").first()
    if not owner:
        print("Owner not found.")
        return

    now = datetime.utcnow()

    # Create Station 1
    station1 = Station(
        name="Trạm sạc Vincom Center",
        address="72 Lê Thánh Tôn, Bến Nghé, Quận 1, TP.HCM",
        latitude=10.7779,
        longitude=106.7024,
        status="active",
        owner_id=owner.id,
        created_at=now,
        updated_at=now
    )
    db.add(station1)
    
    # Create Station 2
    station2 = Station(
        name="Trạm sạc AEON Mall",
        address="30 Bờ Bao Tân Thắng, Sơn Kỳ, Tân Phú, TP.HCM",
        latitude=10.8016,
        longitude=106.6179,
        status="active",
        owner_id=owner.id,
        created_at=now,
        updated_at=now
    )
    db.add(station2)
    db.commit()
    db.refresh(station1)
    db.refresh(station2)

    # Create Charge Points for Station 1
    cp1 = ChargePoint(
        code="CP_VINCOM_01",
        station_id=station1.id,
        vendor="VinFast",
        model="VF-AC-11KW",
        status="online",
        created_at=now,
        updated_at=now
    )
    cp2 = ChargePoint(
        code="CP_VINCOM_02",
        station_id=station1.id,
        vendor="ABB",
        model="Terra 54",
        status="offline",
        created_at=now,
        updated_at=now
    )
    # Create Charge Points for Station 2
    cp3 = ChargePoint(
        code="CP_AEON_01",
        station_id=station2.id,
        vendor="EVN",
        model="EVN-FAST",
        status="online",
        created_at=now,
        updated_at=now
    )
    db.add(cp1)
    db.add(cp2)
    db.add(cp3)
    db.commit()
    db.refresh(cp1)
    db.refresh(cp2)
    db.refresh(cp3)

    # Create Connectors
    # cp1 has 2 connectors
    c1 = Connector(charge_point_id=cp1.id, connector_id=1, status="available", created_at=now, updated_at=now)
    c2 = Connector(charge_point_id=cp1.id, connector_id=2, status="charging", created_at=now, updated_at=now)
    
    # cp2 has 1 connector
    c3 = Connector(charge_point_id=cp2.id, connector_id=1, status="unavailable", created_at=now, updated_at=now)
    
    # cp3 has 3 connectors
    c4 = Connector(charge_point_id=cp3.id, connector_id=1, status="available", created_at=now, updated_at=now)
    c5 = Connector(charge_point_id=cp3.id, connector_id=2, status="available", created_at=now, updated_at=now)
    c6 = Connector(charge_point_id=cp3.id, connector_id=3, status="faulted", created_at=now, updated_at=now)

    db.add_all([c1, c2, c3, c4, c5, c6])
    db.commit()

    print("Successfully seeded demo data for stations, charge points, and connectors.")

if __name__ == "__main__":
    seed_data()
