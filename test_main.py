from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, ShortURL, get_db
from main import BASE_PREFIX, DEFAULT_PORT, app, normalize_prefix
from metadata_scraper import parse_html_metadata

TEST_DB_URL = "sqlite:///./test_shorturl.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    import os
    if os.path.exists("./test_shorturl.db"):
        os.remove("./test_shorturl.db")


def test_default_prefix_and_root_redirect():
    assert DEFAULT_PORT == 5000
    assert BASE_PREFIX == "/shorturl"
    assert normalize_prefix(None) == "/shorturl"
    assert normalize_prefix("my-subpath") == "/my-subpath"
    assert normalize_prefix("/custom/") == "/custom"
    assert normalize_prefix("/") == ""

    # Healthcheck endpoint works under prefix and root
    status_res = client.get(f"{BASE_PREFIX}/api/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "ok"
    assert status_res.json()["prefix"] == BASE_PREFIX

    root_status_res = client.get("/api/status")
    assert root_status_res.status_code == 200
    assert root_status_res.json()["status"] == "ok"

    # Root '/' redirects to '/shorturl/'
    root_res = client.get("/", follow_redirects=False)
    assert root_res.status_code == 307
    assert root_res.headers["location"] == f"{BASE_PREFIX}/"

    # Dashboard at '/shorturl' and '/shorturl/' renders properly
    res = client.get(f"{BASE_PREFIX}/")
    assert res.status_code == 200
    assert "ShortURL" in res.text
    assert "custom-description" in res.text
    assert f'window.BASE_PREFIX = "{BASE_PREFIX}"' in res.text


def test_parse_html_metadata_unit():
    sample_html = """
    <html>
      <head>
        <title>Fallback Title</title>
        <meta property="og:title" content="OpenGraph Test Title" />
        <meta property="og:description" content="Preview description for target site" />
        <meta property="og:image" content="/assets/preview.png" />
        <link rel="icon" href="/favicon-32x32.png" />
      </head>
      <body>Hello</body>
    </html>
    """
    parsed = parse_html_metadata(sample_html, "https://example.com/page")
    assert parsed["meta_title"] == "OpenGraph Test Title"
    assert parsed["meta_description"] == "Preview description for target site"
    assert parsed["meta_image"] == "https://example.com/assets/preview.png"
    assert parsed["favicon_url"] == "https://example.com/favicon-32x32.png"


def test_create_default_one_year_expiry_and_instant_redirect_meta_page(monkeypatch):
    def fake_fetch_meta(url: str, timeout: float = 4.0):
        return {
            "meta_title": "FastAPI Official Site",
            "meta_description": "FastAPI framework, high performance, easy to learn",
            "meta_image": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
            "favicon_url": "https://fastapi.tiangolo.com/img/favicon.png",
            "meta_updated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr("main.fetch_url_metadata", fake_fetch_meta)

    res = client.post(
        f"{BASE_PREFIX}/api/urls",
        json={"original_url": "https://fastapi.tiangolo.com"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["meta_title"] == "FastAPI Official Site"
    assert data["expires_at"] is not None
    assert data["short_url"].endswith(f"{BASE_PREFIX}/{data['short_code']}")

    # Verify default expiration is roughly 365 days from created_at
    created_dt = datetime.fromisoformat(data["created_at"])
    expires_dt = datetime.fromisoformat(data["expires_at"])
    diff_days = (expires_dt - created_dt).days
    assert 364 <= diff_days <= 366

    # Accessing {BASE_PREFIX}/{short_code} provides OG preview metadata and immediate redirect
    code = data["short_code"]
    landing_res = client.get(f"{BASE_PREFIX}/{code}", follow_redirects=False)
    assert landing_res.status_code == 200
    assert 'property="og:title" content="FastAPI Official Site"' in landing_res.text
    assert 'property="og:description" content="FastAPI framework, high performance, easy to learn"' in landing_res.text
    assert 'property="og:image" content="https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"' in landing_res.text
    assert 'http-equiv="refresh" content="0; url=https://fastapi.tiangolo.com/"' in landing_res.text
    assert 'window.location.replace("https://fastapi.tiangolo.com/")' in landing_res.text

    # Clicks should be 1
    info_res = client.get(f"{BASE_PREFIX}/api/urls/{code}")
    assert info_res.status_code == 200
    assert info_res.json()["clicks"] == 1


def test_custom_description_reflected_in_metadata_and_preserved_on_refresh(monkeypatch):
    state = {"title": "Initial Title", "desc": "Scraped Site Description"}

    def fake_fetch_meta(url: str, timeout: float = 4.0):
        return {
            "meta_title": state["title"],
            "meta_description": state["desc"],
            "meta_image": "https://example.com/thumb.png",
            "favicon_url": "https://example.com/favicon.ico",
            "meta_updated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr("main.fetch_url_metadata", fake_fetch_meta)

    create_res = client.post(
        f"{BASE_PREFIX}/api/urls",
        json={
            "original_url": "https://example.com/article",
            "custom_alias": "news-1",
            "custom_description": "사용자가 직접 입력한 커스텀 링크 설명입니다.",
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["custom_description"] == "사용자가 직접 입력한 커스텀 링크 설명입니다."
    assert created["meta_description"] == "사용자가 직접 입력한 커스텀 링크 설명입니다."

    # Verify OG meta tag on {BASE_PREFIX}/{short_code} reflects the user's custom description
    page_res = client.get(f"{BASE_PREFIX}/news-1")
    assert page_res.status_code == 200
    assert 'property="og:description" content="사용자가 직접 입력한 커스텀 링크 설명입니다."' in page_res.text

    # Refresh metadata updates title/image from target site while keeping user custom_description
    state["title"] = "Updated Breaking News Title"
    refresh_res = client.post(f"{BASE_PREFIX}/api/urls/news-1/refresh-meta")
    assert refresh_res.status_code == 200
    refreshed_data = refresh_res.json()
    assert refreshed_data["meta_title"] == "Updated Breaking News Title"
    assert refreshed_data["meta_description"] == "사용자가 직접 입력한 커스텀 링크 설명입니다."

    # Clearing custom description via PATCH falls back to scraped description
    patch_res = client.patch(
        f"{BASE_PREFIX}/api/urls/news-1/description", json={"custom_description": ""}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["custom_description"] is None
    assert patch_res.json()["meta_description"] == "Scraped Site Description"


def test_expired_link_and_purge(monkeypatch):
    monkeypatch.setattr(
        "main.fetch_url_metadata",
        lambda url, timeout=4.0: {
            "meta_title": "Temp Page",
            "meta_description": "Desc",
            "meta_image": None,
            "favicon_url": None,
            "meta_updated_at": datetime.now(timezone.utc),
        },
    )

    res = client.post(
        f"{BASE_PREFIX}/api/urls",
        json={"original_url": "https://example.com/old", "custom_alias": "old-link"},
    )
    assert res.status_code == 201

    # Simulate 1 year elapsed in DB
    db = TestingSessionLocal()
    item = db.query(ShortURL).filter(ShortURL.short_code == "old-link").first()
    item.created_at = datetime.now(timezone.utc) - timedelta(days=366)
    item.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    db.close()

    # Should return 410 Gone
    r_res = client.get(f"{BASE_PREFIX}/old-link", follow_redirects=False)
    assert r_res.status_code == 410

    # Purge expired links
    purge_res = client.delete(f"{BASE_PREFIX}/api/urls/expired/purge")
    assert purge_res.status_code == 200
    assert purge_res.json()["purged_count"] == 1

    # Now should be 404 Not Found
    after_purge = client.get(f"{BASE_PREFIX}/old-link", follow_redirects=False)
    assert after_purge.status_code == 404
