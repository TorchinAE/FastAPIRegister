import pytest


async def _create_position(client, name="ТестДолжность"):
    resp = await client.post("/api/positions/", json={"name": name})
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_position(client):
    data = await _create_position(client, "Инженер")
    assert data["name"] == "Инженер"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_positions(client):
    await _create_position(client, "Менеджер")
    resp = await client.get("/api/positions/")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_get_position_by_id(client):
    created = await _create_position(client, "Аналитик")
    resp = await client.get(f"/api/positions/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Аналитик"


@pytest.mark.asyncio
async def test_get_position_not_found(client):
    resp = await client.get("/api/positions/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_position(client):
    created = await _create_position(client, "Старый")
    resp = await client.patch("/api/positions/", json={
        "id": created["id"],
        "name": "Новый",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новый"


@pytest.mark.asyncio
async def test_update_position_not_found(client):
    resp = await client.patch("/api/positions/", json={
        "id": 99999,
        "name": "Нет",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_position(client):
    created = await _create_position(client, "Удалить")
    resp = await client.delete(f"/api/positions/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/positions/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_position_not_found(client):
    resp = await client.delete("/api/positions/99999")
    assert resp.status_code == 404
