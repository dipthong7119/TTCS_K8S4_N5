"""T-24/T-25: HTML must not reuse stale monitoring scripts after a frontend update."""

import os
import re

import pytest

from app.routers import pages


def test_asset_url_changes_for_same_size_file_update(tmp_path, monkeypatch):
    asset = tmp_path / "static" / "js" / "monitoring.js"
    asset.parent.mkdir(parents=True)
    asset.write_text("before", encoding="utf-8")
    monkeypatch.setattr(pages, "_templates_dir", tmp_path / "templates")
    previous_url = pages.asset_url("js/monitoring.js")
    previous_stat = asset.stat()

    asset.write_text("after!", encoding="utf-8")
    os.utime(asset, ns=(previous_stat.st_atime_ns, previous_stat.st_mtime_ns + 1_000_000_000))

    assert asset.stat().st_size == previous_stat.st_size
    assert pages.asset_url("js/monitoring.js") != previous_url
    assert pages.asset_url("js/monitoring.js") == pages.asset_url("js/monitoring.js")


@pytest.mark.parametrize(
    ("role", "page"),
    [
        ("admin", "/login"),
        ("admin", "/monitoring"),
        ("operator", "/monitoring"),
        ("station_owner", "/monitoring"),
        ("admin", "/stations"),
        ("admin", "/stations/new"),
        ("admin", "/sessions"),
        ("admin", "/sessions/anomalies"),
        ("admin", "/audit"),
        ("admin", "/wallet"),
        ("driver", "/wallet"),
        ("driver", "/sessions/mine"),
    ],
)
def test_rendered_pages_use_loadable_versioned_assets(client, user_factory, role, page):
    user = user_factory(role_name=role)
    assert client.post(
        "/api/auth/login", json={"email": user.email, "password": "ValidPassword123!"}
    ).status_code == 200

    response = client.get(page)
    assert response.status_code == 200
    assets = re.findall(r'(?:src|href)="(/static/(?:js|css)/[^"]+)"', response.text)
    assert assets
    for url in assets:
        assert "?v=" in url, url
        assert client.get(url).status_code == 200, url
    if page == "/monitoring":
        assert "realtime_status.js" not in response.text
        assert any("pages/monitoring_grid.js?v=" in url for url in assets)


def test_monitoring_logout_form_clears_session(client, user_factory):
    user = user_factory(role_name="admin")
    assert client.post(
        "/api/auth/login", json={"email": user.email, "password": "ValidPassword123!"}
    ).status_code == 200
    assert 'action="/auth/logout" method="post"' in client.get("/monitoring").text
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    assert client.get("/api/monitoring/tree").status_code == 401


@pytest.mark.parametrize("url", ["/login", "/login?mock=1"])
def test_login_has_no_simulated_login_mode(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert "login-mock-notice" not in response.text
    assert "mock@example.test" not in response.text
    assert "Chế độ mock" not in response.text
