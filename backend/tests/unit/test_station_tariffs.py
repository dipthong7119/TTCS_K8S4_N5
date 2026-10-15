"""SCRUM-62: validate daily station tariff bands on the backend."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.station import Station
from app.models.station_tariff import TariffBand
from app.models.user import Role, User


@pytest.fixture
def tariff_client(db_session) -> Generator[TestClient, None, None]:
    previous_overrides = dict(app.dependency_overrides)

    def override_get_db():
        yield db_session

    owner = User(
        id=901,
        email="tariff-owner@example.test",
        password_hash="test-hash",
        full_name="Tariff Owner",
        is_active=True,
    )
    role = Role(id=901, name="station_owner")
    owner.roles = [role]
    db_session.add_all([owner, role])
    db_session.flush()
    db_session.add(Station(id=901, name="Tariff Station", owner_id=owner.id, status="active"))
    db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=owner.id, roles=[role]
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_create_station_tariff_splits_overnight_band(tariff_client, db_session) -> None:
    response = tariff_client.post(
        "/api/stations/901/tariffs",
        json={
            "name": "Tariff with overnight rate",
            "timezone_name": "UTC",
            "bands": [
                {
                    "label": "Night rate",
                    "start_minute": 1320,
                    "end_minute": 120,
                    "price_vnd_per_kwh": 3000,
                },
                {
                    "label": "Day rate",
                    "start_minute": 120,
                    "end_minute": 1320,
                    "price_vnd_per_kwh": 5000,
                },
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["price_vnd_per_kwh"] is None
    assert [
        (band["start_minute"], band["end_minute"], band["label"])
        for band in data["bands"]
    ] == [
        (0, 120, "Night rate"),
        (120, 1320, "Day rate"),
        (1320, 1440, "Night rate"),
    ]
    assert (
        db_session.query(TariffBand)
        .filter_by(tariff_id=data["id"])
        .count()
        == 3
    )


@pytest.mark.parametrize(
    ("bands", "expected_detail"),
    [
        (
            [
                {"label": "Night", "start_minute": 0, "end_minute": 360, "price_vnd_per_kwh": 3000},
                {"label": "Day", "start_minute": 420, "end_minute": 1440, "price_vnd_per_kwh": 4000},
            ],
            "Biểu giá bị hở từ 06:00 đến 07:00",
        ),
        (
            [
                {"label": "Night", "start_minute": 0, "end_minute": 420, "price_vnd_per_kwh": 3000},
                {"label": "Day", "start_minute": 360, "end_minute": 1440, "price_vnd_per_kwh": 4000},
            ],
            "Biểu giá bị chồng lấn từ 06:00 đến 07:00",
        ),
    ],
)
def test_create_station_tariff_rejects_gaps_and_overlaps(
    tariff_client, bands, expected_detail
) -> None:
    response = tariff_client.post(
        "/api/stations/901/tariffs",
        json={"name": "Invalid tariff", "bands": bands},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == expected_detail


def test_create_station_tariff_keeps_flat_rate_api_compatible(tariff_client) -> None:
    response = tariff_client.post(
        "/api/stations/901/tariffs",
        json={"name": "Flat tariff", "price_vnd_per_kwh": 4000},
    )

    assert response.status_code == 201
    assert response.json()["price_vnd_per_kwh"] == 4000
    assert response.json()["bands"] == [
        {
            "label": "Cả ngày",
            "start_minute": 0,
            "end_minute": 1440,
            "price_vnd_per_kwh": 4000,
        }
    ]


def test_create_station_tariff_rejects_effective_time_in_the_past(tariff_client) -> None:
    response = tariff_client.post(
        "/api/stations/901/tariffs",
        json={
            "name": "Past tariff",
            "price_vnd_per_kwh": 4000,
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Thời điểm hiệu lực không được nằm trong quá khứ"
