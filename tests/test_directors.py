import pytest


async def _create_position(client, name):
    resp = await client.post("/api/positions/", json={"name": name})
    return resp.json()


async def _create_director(client, position_id, name="Иванов Иван Иванович", email="ivan@dir.ru"):
    resp = await client.post("/api/directors/", json={
        "name": name,
        "email": email,
        "phone": "+79991112233",
        "position_id": position_id,
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_director(client):
    pos = await _create_position(client, "ДирТест")
    data = await _create_director(client, pos["id"], "Петров Пётр Петрович", "petrov@dir.ru")
    assert data["name"] == "Петров Пётр Петрович"
    assert data["position"]["id"] == pos["id"]


@pytest.mark.asyncio
async def test_list_directors(client):
    pos = await _create_position(client, "ДирСписок")
    await _create_director(client, pos["id"], "Сидоров Сидор Сидорович", "sidorov@dir.ru")
    resp = await client.get("/api/directors/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_director_by_id(client):
    pos = await _create_position(client, "ДирПолуч")
    created = await _create_director(client, pos["id"], "Козлов Козьма Козьмич", "kozlov@dir.ru")
    resp = await client.get(f"/api/directors/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Козлов Козьма Козьмич"


@pytest.mark.asyncio
async def test_get_director_not_found(client):
    resp = await client.get("/api/directors/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_director(client):
    pos = await _create_position(client, "ДирОбнов")
    created = await _create_director(client, pos["id"], "Старый Фамилия Отчество", "old@dir.ru")
    resp = await client.patch("/api/directors/", json={
        "id": created["id"],
        "name": "Новый Фамилия Отчество",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новый Фамилия Отчество"


@pytest.mark.asyncio
async def test_update_director_not_found(client):
    resp = await client.patch("/api/directors/", json={"id": 99999, "name": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_director(client):
    pos = await _create_position(client, "ДирУдал")
    created = await _create_director(client, pos["id"], "Удаляем Удалён Удалёнович", "del@dir.ru")
    resp = await client.delete(f"/api/directors/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/directors/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_director_not_found(client):
    resp = await client.delete("/api/directors/99999")
    assert resp.status_code == 404
