import pytest


async def _create_section(client, name="ТестСекция"):
    resp = await client.post("/api/equipment-sections/", json={"name": name})
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_section(client):
    data = await _create_section(client, "ВА-100")
    assert data["name"] == "ВА-100"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_sections(client):
    await _create_section(client, "Schnaider-200")
    resp = await client.get("/api/equipment-sections/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_get_section_by_id(client):
    created = await _create_section(client, "IEK-300")
    resp = await client.get(f"/api/equipment-sections/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "IEK-300"


@pytest.mark.asyncio
async def test_get_section_not_found(client):
    resp = await client.get("/api/equipment-sections/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_section(client):
    created = await _create_section(client, "Старое")
    resp = await client.put(f"/api/equipment-sections/{created['id']}", json={
        "id": created["id"],
        "name": "Новое",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новое"


@pytest.mark.asyncio
async def test_update_section_not_found(client):
    resp = await client.put("/api/equipment-sections/99999", json={"id": 99999, "name": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_section(client):
    created = await _create_section(client, "Удалить")
    resp = await client.delete(f"/api/equipment-sections/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/equipment-sections/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_section_not_found(client):
    resp = await client.delete("/api/equipment-sections/99999")
    assert resp.status_code == 404
