import pytest


@pytest.mark.asyncio
async def test_read_settings_empty(client):
    resp = await client.get("/api/settings/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


@pytest.mark.asyncio
async def test_upsert_setting(client):
    resp = await client.put("/api/settings/", json={
        "key": "test_key",
        "value": "test_value",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_read_settings_after_upsert(client):
    await client.put("/api/settings/", json={"key": "k1", "value": "v1"})
    await client.put("/api/settings/", json={"key": "k2", "value": "v2"})
    resp = await client.get("/api/settings/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["k1"] == "v1"
    assert data["k2"] == "v2"


@pytest.mark.asyncio
async def test_upsert_setting_overwrite(client):
    await client.put("/api/settings/", json={"key": "overwrite", "value": "old"})
    await client.put("/api/settings/", json={"key": "overwrite", "value": "new"})
    resp = await client.get("/api/settings/")
    assert resp.json()["overwrite"] == "new"
