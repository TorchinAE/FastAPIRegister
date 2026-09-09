import pytest


async def _create_equipment(client, name="ТестОборудование"):
    resp = await client.post("/api/equipment/", json={"name": name})
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_equipment(client):
    data = await _create_equipment(client, "КТПБ-1000")
    assert data["name"] == "КТПБ-1000"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_equipment(client):
    await _create_equipment(client, "КСО-393")
    resp = await client.get("/api/equipment/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_equipment_by_id(client):
    created = await _create_equipment(client, "ЩО-12")
    resp = await client.get(f"/api/equipment/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "ЩО-12"


@pytest.mark.asyncio
async def test_get_equipment_not_found(client):
    resp = await client.get("/api/equipment/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_equipment(client):
    created = await _create_equipment(client, "Старое")
    resp = await client.patch("/api/equipment/", json={
        "id": created["id"],
        "name": "Новое",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новое"


@pytest.mark.asyncio
async def test_update_equipment_not_found(client):
    resp = await client.patch("/api/equipment/", json={"id": 99999, "name": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_equipment(client):
    created = await _create_equipment(client, "Удалить")
    resp = await client.delete(f"/api/equipment/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/equipment/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_equipment_not_found(client):
    resp = await client.delete("/api/equipment/99999")
    assert resp.status_code == 404
