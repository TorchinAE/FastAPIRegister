import pytest
import uuid


async def _create_position(client, name):
    resp = await client.post("/api/positions/", json={"name": name})
    return resp.json()


async def _create_director(client, position_id, name, email):
    resp = await client.post("/api/directors/", json={
        "name": name,
        "email": email,
        "position_id": position_id,
    })
    return resp.json()


_inn_counter = 0


async def _create_company(client, director_id, name='ООО "Тест"'):
    global _inn_counter
    _inn_counter += 1
    resp = await client.post("/api/companies/", json={
        "name": name,
        "inn": f"77{_inn_counter:010d}",
        "address": "г. Москва",
        "director_id": director_id,
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_company(client):
    pos = await _create_position(client, "КомпДолж")
    d = await _create_director(client, pos["id"], "Дир Компании", "dir@comp.ru")
    data = await _create_company(client, d["id"], 'ООО "Альфа"')
    assert data["name"] == 'ООО "Альфа"'
    assert data["director_id"] == d["id"]


@pytest.mark.asyncio
async def test_list_companies(client):
    pos = await _create_position(client, "КомпСписок")
    d = await _create_director(client, pos["id"], "Дир Список", "list@comp.ru")
    await _create_company(client, d["id"], 'ООО "Бета"')
    resp = await client.get("/api/companies/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_company_by_id(client):
    pos = await _create_position(client, "КомпПолуч")
    d = await _create_director(client, pos["id"], "Дир Получ", "get@comp.ru")
    created = await _create_company(client, d["id"], 'ООО "Гамма"')
    resp = await client.get(f"/api/companies/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == 'ООО "Гамма"'


@pytest.mark.asyncio
async def test_get_company_not_found(client):
    resp = await client.get("/api/companies/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_company(client):
    pos = await _create_position(client, "КомпОбнов")
    d = await _create_director(client, pos["id"], "Дир Обнов", "upd@comp.ru")
    created = await _create_company(client, d["id"], 'ООО "Старое"')
    resp = await client.patch("/api/companies/", json={
        "id": created["id"],
        "name": 'ООО "Новое"',
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == 'ООО "Новое"'


@pytest.mark.asyncio
async def test_update_company_not_found(client):
    resp = await client.patch("/api/companies/", json={"id": 99999, "name": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_company(client):
    pos = await _create_position(client, "КомпУдал")
    d = await _create_director(client, pos["id"], "Дир Удал", "del@comp.ru")
    created = await _create_company(client, d["id"], 'ООО "Удалить"')
    resp = await client.delete(f"/api/companies/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/companies/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_company_not_found(client):
    resp = await client.delete("/api/companies/99999")
    assert resp.status_code == 404
