import pytest
import uuid


async def _setup_full(client):
    """Create position → director → company → counterparty → user, return all."""
    uid = uuid.uuid4().hex[:8]
    pos = (await client.post("/api/positions/", json={"name": f"ЗапДолж-{uid}"})).json()
    d = (await client.post("/api/directors/", json={
        "name": f"Дир Запроса {uid}", "email": f"dir_{uid}@req.ru", "position_id": pos["id"],
    })).json()
    inn = str(3000000000 + hash(uid) % 8999999999)[:10]
    comp = (await client.post("/api/companies/", json={
        "name": f'ООО "Запрос-{uid}"', "inn": inn, "director_id": d["id"],
    })).json()
    cp = (await client.post("/api/counterparties/", json={
        "name": f"Контр Запроса {uid}", "email": f"cp_{uid}@req.ru", "company_id": comp["id"],
    })).json()
    user = (await client.post("/api/auth/register", json={
        "name": f"Менеджер Запросов {uid}",
        "email": f"mgr_{uid}@ivn.ruelta.ru",
        "password": "pass",
        "city": "мск",
    })).json()
    return {"pos": pos, "dir": d, "company": comp, "cp": cp, "user": user}


async def _create_request(client, user_id, cp_id, company_id, description="Тестовый запрос"):
    resp = await client.post(f"/api/requests/?manager_id={user_id}", json={
        "counterparty_id": cp_id,
        "company_id": company_id,
        "description": description,
        "status": "запрос",
        "cost": 100000,
        "bktpb": 2,
        "ktpb": 3,
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_create_request(client):
    env = await _setup_full(client)
    data = await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    assert data["description"] == "Тестовый запрос"
    assert data["manager_id"] == env["user"]["id"]
    assert data["status"] == "запрос"


@pytest.mark.asyncio
async def test_list_requests(client):
    env = await _setup_full(client)
    await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    resp = await client.get("/api/requests/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert "items" in body


@pytest.mark.asyncio
async def test_get_request_by_id(client):
    env = await _setup_full(client)
    created = await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    resp = await client.get(f"/api/requests/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_request_not_found(client):
    resp = await client.get("/api/requests/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_request(client):
    env = await _setup_full(client)
    created = await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    resp = await client.put(f"/api/requests/{created['id']}", json={
        "id": created["id"],
        "description": "Обновлённый запрос",
        "cost": 200000,
    })
    assert resp.status_code == 200
    assert resp.json()["description"] == "Обновлённый запрос"


@pytest.mark.asyncio
async def test_update_request_not_found(client):
    resp = await client.put("/api/requests/99999", json={"id": 99999, "description": "Нет"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_request(client):
    env = await _setup_full(client)
    created = await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    resp = await client.delete(f"/api/requests/{created['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/requests/{created['id']}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_request_not_found(client):
    resp = await client.delete("/api/requests/99999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_duplicates_empty(client):
    resp = await client.get("/api/requests/search/duplicates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_search_duplicates_by_stamp(client):
    env = await _setup_full(client)
    req = await _create_request(client, env["user"]["id"], env["cp"]["id"], env["company"]["id"])
    await client.put(f"/api/requests/{req['id']}", json={
        "id": req["id"],
        "project_stamp": "STAMP-001",
    })
    resp = await client.get("/api/requests/search/duplicates?project_stamp=STAMP-001")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
