import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.testclient import TestClient

from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.routers.monitoring import notify_status_change, sse_clients
from app.routers.stations import router as stations_router

PASSWORD = "ValidPassword123!"


def login(client: TestClient, user) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def test_station_create_read_update_delete_ten_times(client, user_factory) -> None:
    owner = user_factory(password=PASSWORD)
    login(client, owner)

    for index in range(10):
        created_response = client.post(
            "/api/stations",
            json={
                "name": f"CRUD station {index}",
                "address": f"Test address {index}",
                "latitude": 10.0 + index / 100,
                "longitude": 106.0 + index / 100,
            },
        )
        assert created_response.status_code == 201, created_response.text
        station = created_response.json()
        assert station["status"] == "active"

        listing = client.get("/api/stations")
        assert listing.status_code == 200
        listed_items = listing.json().get("items", listing.json())
        assert any(item["id"] == station["id"] for item in listed_items)

        updated_response = client.put(
            f"/api/stations/{station['id']}",
            json={
                "name": f"Updated station {index}",
                "address": "Updated address",
                "latitude": None,
            },
        )
        assert updated_response.status_code == 200, updated_response.text
        assert updated_response.json()["name"] == f"Updated station {index}"
        assert updated_response.json()["latitude"] is None

        deleted_response = client.delete(f"/api/stations/{station['id']}")
        assert deleted_response.status_code == 204, deleted_response.text
        assert client.get(f"/api/stations/{station['id']}").status_code == 404


def test_charge_point_create_read_update_delete_ten_times(client, user_factory) -> None:
    owner = user_factory(password=PASSWORD)
    login(client, owner)
    station_response = client.post(
        "/api/stations",
        json={"name": "Charge point CRUD station", "address": "Test address"},
    )
    assert station_response.status_code == 201, station_response.text
    station_id = station_response.json()["id"]

    for index in range(10):
        code = f"CRUD-CP-{index:02d}"
        created_response = client.post(
            "/api/charge-points",
            json={"code": code, "station_id": station_id, "connector_count": 2},
        )
        assert created_response.status_code == 201, created_response.text
        charge_point = created_response.json()
        assert [item["connector_id"] for item in charge_point["connectors"]] == [1, 2]
        assert [item["status"] for item in charge_point["connectors"]] == ["unknown", "unknown"]

        duplicate_create = client.post(
            "/api/charge-points",
            json={"code": code, "station_id": station_id, "connector_count": 2},
        )
        assert duplicate_create.status_code == 409, duplicate_create.text

        duplicate_response = client.get(
            "/api/charge-points/check-code", params={"code": code}
        )
        assert duplicate_response.status_code == 409, duplicate_response.text

        detail_response = client.get(f"/api/charge-points/{charge_point['id']}")
        assert detail_response.status_code == 200, detail_response.text
        update_response = client.patch(
            f"/api/charge-points/{charge_point['id']}",
            json={"vendor": f"Vendor {index}"},
        )
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["vendor"] == f"Vendor {index}"

        delete_response = client.delete(f"/api/charge-points/{charge_point['id']}")
        assert delete_response.status_code == 204, delete_response.text
        assert client.get(f"/api/charge-points/{charge_point['id']}").status_code == 404

    assert client.delete(f"/api/stations/{station_id}").status_code == 204


def test_station_edit_page_loads_existing_station(client, user_factory) -> None:
    owner = user_factory(password=PASSWORD)
    login(client, owner)
    created = client.post(
        "/api/stations",
        json={"name": "Prefilled station", "address": "Station address"},
    )
    station_id = created.json()["id"]

    response = client.get(f"/stations/{station_id}/edit")

    assert response.status_code == 200
    assert f'name="station_id" value="{station_id}"' in response.text
    assert 'value="Prefilled station"' in response.text
    assert "Station address" in response.text


def test_owner_cannot_list_charge_points_from_another_owner(client, db_session, user_factory) -> None:
    owner_a = user_factory(email="owner-a@example.com", password=PASSWORD)
    owner_b = user_factory(email="owner-b@example.com", password=PASSWORD)
    station = Station(name="Private station", address="Private", owner_id=owner_b.id)
    db_session.add(station)
    db_session.flush()
    charge_point = ChargePoint(code="PRIVATE-CP", station_id=station.id)
    db_session.add(charge_point)
    db_session.commit()
    station_id = station.id

    login(client, owner_a)
    response = client.get("/api/charge-points", params={"station_id": station_id})

    assert response.status_code == 403, response.text


def test_station_owner_cannot_read_foreign_station_and_attempt_is_logged(
    client, db_session, user_factory
) -> None:
    owner_a = user_factory(email="station-reader@example.com", password=PASSWORD)
    owner_b = user_factory(email="station-private@example.com", password=PASSWORD)
    station = Station(name="Private station", address="Private", owner_id=owner_b.id)
    db_session.add(station)
    db_session.commit()

    login(client, owner_a)
    with patch("app.services.ownership.logger.warning") as log_warning:
        response = client.get(f"/api/stations/{station.id}")

    assert response.status_code == 403, response.text
    log_warning.assert_called_once()
    assert "station_access_denied" in log_warning.call_args.args[0]


def test_owner_cannot_add_charge_point_to_another_owners_station(
    client, db_session, user_factory
) -> None:
    owner_a = user_factory(email="adder@example.com", password=PASSWORD)
    owner_b = user_factory(email="station-owner@example.com", password=PASSWORD)
    station = Station(name="Foreign station", address="Private", owner_id=owner_b.id)
    db_session.add(station)
    db_session.commit()

    login(client, owner_a)
    response = client.post(
        "/api/charge-points",
        json={"code": "FORBIDDEN-CP", "station_id": station.id},
    )

    assert response.status_code == 403, response.text


def test_driver_is_denied_operator_monitoring_route(client, user_factory) -> None:
    driver = user_factory(email="driver-route@example.com", password=PASSWORD, role_name="driver")
    login(client, driver)

    response = client.get("/api/monitoring/tree")

    assert response.status_code == 403, response.text


def test_station_pages_require_login_and_operator_is_read_only(client, user_factory) -> None:
    assert client.get("/stations").status_code == 401

    driver = user_factory(email="driver-pages@example.com", role_name="driver")
    login(client, driver)
    assert client.get("/stations/new").status_code == 403

    client.post("/api/auth/logout")
    operator = user_factory(email="operator-pages@example.com", role_name="operator")
    login(client, operator)
    response = client.get("/stations")

    assert response.status_code == 200, response.text
    assert 'data-can-manage-stations="false"' in response.text
    assert 'id="btn-add-station"' not in response.text


def test_monitoring_events_are_scoped_to_station_owner_or_global_roles() -> None:
    owner_queue = asyncio.Queue()
    other_owner_queue = asyncio.Queue()
    operator_queue = asyncio.Queue()
    subscriptions = [
        {"queue": owner_queue, "owner_id": 10, "global_access": False},
        {"queue": other_owner_queue, "owner_id": 11, "global_access": False},
        {"queue": operator_queue, "owner_id": 12, "global_access": True},
    ]
    sse_clients.extend(subscriptions)
    try:
        notify_status_change(5, [{"code": "CP-5"}], owner_id=10)

        assert owner_queue.get_nowait()["event"] == "status_update"
        assert operator_queue.get_nowait()["event"] == "status_update"
        with pytest.raises(asyncio.QueueEmpty):
            other_owner_queue.get_nowait()
    finally:
        for subscription in subscriptions:
            sse_clients.remove(subscription)


def test_unannotated_route_inherits_default_deny() -> None:
    probe_router = APIRouter(dependencies=stations_router.dependencies)

    @probe_router.get("/unannotated")
    async def unannotated_route():
        return {"exposed": True}

    app = FastAPI()
    app.include_router(probe_router)

    with TestClient(app) as client:
        response = client.get("/unannotated")

    assert response.status_code == 403, response.text
