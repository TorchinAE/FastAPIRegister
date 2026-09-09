import pytest
import uuid


async def _setup_request(client):
    uid = uuid.uuid4().hex[:8]
    pos = (await client.post("/api/positions/", json={"name": f"СчДолж-{uid}"})).json()
    d = (await client.post("/api/directors/", json={
        "name": f"Дир Счёта {uid}", "email": f"dir_{uid}@inv.ru", "position_id": pos["id"],
    })).json()
    inn = str(1000000000 + hash(uid) % 8999999999)[:10]
    comp = (await client.post("/api/companies/", json={
        "name": f'ООО "Счёт-{uid}"', "inn": inn, "director_id": d["id"],
    })).json()
    cp = (await client.post("/api/counterparties/", json={
        "name": f"Контр Счёта {uid}", "email": f"cp_{uid}@inv.ru", "company_id": comp["id"],
    })).json()
    user = (await client.post("/api/auth/register", json={
        "name": f"Менеджер Счётов {uid}", "email": f"mgr_{uid}@ivn.ruelta.ru", "password": "pass",
    })).json()
    req = (await client.post(f"/api/requests/?manager_id={user['id']}", json={
        "counterparty_id": cp["id"],
        "company_id": comp["id"],
        "description": "Запрос для счёта",
    })).json()
    return req


@pytest.mark.asyncio
async def test_create_invoice(client):
    req = await _setup_request(client)
    resp = await client.post("/api/invoices/", json={
        "request_id": req["id"],
        "invoice_num": "INV-001",
        "percent": 50,
        "amount": 50000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoice_num"] == "INV-001"
    assert data["request_id"] == req["id"]


@pytest.mark.asyncio
async def test_list_invoices_by_request(client):
    req = await _setup_request(client)
    await client.post("/api/invoices/", json={
        "request_id": req["id"],
        "invoice_num": "INV-002",
        "amount": 30000,
    })
    resp = await client.get(f"/api/invoices/by-request/{req['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["request_id"] == req["id"]


@pytest.mark.asyncio
async def test_update_invoice(client):
    req = await _setup_request(client)
    inv = (await client.post("/api/invoices/", json={
        "request_id": req["id"],
        "invoice_num": "INV-003",
        "amount": 10000,
    })).json()
    resp = await client.put(f"/api/invoices/{inv['id']}", json={
        "id": inv["id"],
        "amount": 20000,
        "paid_amount": 20000,
    })
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 20000


@pytest.mark.asyncio
async def test_update_invoice_not_found(client):
    resp = await client.put("/api/invoices/99999", json={"id": 99999, "amount": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_invoice(client):
    req = await _setup_request(client)
    inv = (await client.post("/api/invoices/", json={
        "request_id": req["id"],
        "invoice_num": "INV-DEL",
        "amount": 5000,
    })).json()
    resp = await client.delete(f"/api/invoices/{inv['id']}")
    assert resp.status_code == 200
    resp2 = await client.get(f"/api/invoices/by-request/{req['id']}")
    assert all(i["id"] != inv["id"] for i in resp2.json())


@pytest.mark.asyncio
async def test_delete_invoice_not_found(client):
    resp = await client.delete("/api/invoices/99999")
    assert resp.status_code == 404
