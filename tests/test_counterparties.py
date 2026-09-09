import pytest


async def _setup_company(client):
    pos_resp = await client.post("/api/positions/", json={"name": "КонтрДолж"})
    pos = pos_resp.json()
    dir_resp = await client.post("/api/directors/", json={
        "name": "Дир Контрагента", "email": "dir@cp.ru", "position_id": pos["id"],
    })
    d = dir_resp.json()
    comp_resp = await client.post("/api/companies/", json={
        "name": 'ООО "Контр"', "director_id": d["id"],
    })
    return comp_resp.json()


async def _create_counterparty(client, company_id, name="Иванов Иван", email="ivan@cp.ru"):
    resp = await client.post("/api/counterparties/", json={
        "name": name,
        "email": email,
        "phone": "+79990001122",
        "company_id": company_id,
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_counterparty(client):
    comp = await _setup_company(client)
    data = await _create_counterparty(client, comp["id"], "Петров Пётр", "petrov@cp.ru")
    assert data["name"] == "Петров Пётр"
    assert data["company_id"] == comp["id"]


@pytest.mark.asyncio
async def test_list_counterparties(client):
    comp = await _setup_company(client)
    await _create_counterparty(client, comp["id"], "Сидоров Сидор", "sidor@cp.ru")
    resp = await client.get("/api/counterparties/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_counterparty_by_id(client):
    comp = await _setup_company(client)
    created = await _create_counterparty(client, comp["id"], "Козлов Козьма", "kozlov@cp.ru")
    resp = await client.get(f"/api/counterparties/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Козлов Козьма"


@pytest.mark.asyncio
async def test_get_counterparty_not_found(client):
    resp = await client.get("/api/counterparties/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_counterparty(client):
    comp = await _setup_company(client)
    created = await _create_counterparty(client, comp["id"], "Старый ФИО", "old@cp.ru")
    resp = await client.patch("/api/counterparties/", json={
        "id": created["id"],
        "name": "Новый ФИО",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новый ФИО"


@pytest.mark.asyncio
async def test_update_counterparty_not_found(client):
    resp = await client.patch("/api/counterparties/", json={"id": 99999, "name": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_counterparty(client):
    comp = await _setup_company(client)
    created = await _create_counterparty(client, comp["id"], "Удаляемый", "del@cp.ru")
    resp = await client.delete(f"/api/counterparties/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/counterparties/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_counterparty_not_found(client):
    resp = await client.delete("/api/counterparties/99999")
    assert resp.status_code == 404
