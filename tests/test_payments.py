import pytest
import uuid


async def _setup_request(client):
    uid = uuid.uuid4().hex[:8]
    pos = (await client.post("/api/positions/", json={"name": f"ПлДолж-{uid}"})).json()
    d = (await client.post("/api/directors/", json={
        "name": f"Дир Платежа {uid}", "email": f"dir_{uid}@pay.ru", "position_id": pos["id"],
    })).json()
    inn = str(2000000000 + hash(uid) % 8999999999)[:10]
    comp = (await client.post("/api/companies/", json={
        "name": f'ООО "Платёж-{uid}"', "inn": inn, "director_id": d["id"],
    })).json()
    cp = (await client.post("/api/counterparties/", json={
        "name": f"Контр Платежа {uid}", "email": f"cp_{uid}@pay.ru", "company_id": comp["id"],
    })).json()
    user = (await client.post("/api/auth/register", json={
        "name": f"Менеджер Платежей {uid}", "email": f"mgr_{uid}@ivn.ruelta.ru", "password": "pass",
    })).json()
    req = (await client.post(f"/api/requests/?manager_id={user['id']}", json={
        "counterparty_id": cp["id"],
        "company_id": comp["id"],
        "description": "Запрос для платежей",
    })).json()
    return req


@pytest.mark.asyncio
async def test_get_payment_items(client):
    req = await _setup_request(client)
    resp = await client.get(f"/api/payments/by-request/{req['id']}")
    assert resp.status_code == 200
    data = resp.json()
    # ensure_payment_items creates all PAYMENT_TYPES
    assert len(data) == 5
    types = {p["payment_type"] for p in data}
    assert "предоплата" in types
    assert "отсрочка" in types


@pytest.mark.asyncio
async def test_update_payment_item(client):
    req = await _setup_request(client)
    items = (await client.get(f"/api/payments/by-request/{req['id']}")).json()
    item_id = items[0]["id"]
    resp = await client.put(f"/api/payments/{item_id}", json={
        "id": item_id,
        "amount": 15000,
        "paid_amount": 10000,
    })
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 15000


@pytest.mark.asyncio
async def test_update_payment_item_not_found(client):
    resp = await client.put("/api/payments/99999", json={"id": 99999, "amount": 1})
    assert resp.status_code == 404
