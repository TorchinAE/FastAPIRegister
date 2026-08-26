import pytest


@pytest.mark.asyncio
async def test_create_simple_product(client):
    resp = await client.post("/api/calc-products/", json={"name": "Простой"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Простой"
    assert data["is_composite"] is False


@pytest.mark.asyncio
async def test_create_composite_product(client):
    resp = await client.post("/api/calc-products/", json={
        "name": "Составной",
        "components": [{"equipment_id": 1, "quantity": 2}]
    })
    assert resp.status_code == 200
    assert resp.json()["is_composite"] is True


@pytest.mark.asyncio
async def test_list_products(client):
    await client.post("/api/calc-products/", json={"name": "ДляСписка"})
    resp = await client.get("/api/calc-products/")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_product_detail(client):
    create = await client.post("/api/calc-products/", json={
        "name": "Детали", "components": [{"equipment_id": 1, "quantity": 3}]
    })
    resp = await client.get(f"/api/calc-products/{create.json()['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["components"]) == 1
    assert data["components"][0]["quantity"] == 3


@pytest.mark.asyncio
async def test_update_product(client):
    create = await client.post("/api/calc-products/", json={"name": "Старое"})
    resp = await client.put(f"/api/calc-products/{create.json()['id']}", json={
        "id": create.json()["id"], "name": "Новое"
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Новое"


@pytest.mark.asyncio
async def test_delete_product(client):
    create = await client.post("/api/calc-products/", json={"name": "Удалить"})
    resp = await client.delete(f"/api/calc-products/{create.json()['id']}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expand_product(client):
    create = await client.post("/api/calc-products/", json={
        "name": "Развернуть", "components": [{"equipment_id": 1, "quantity": 2}]
    })
    resp = await client.get(f"/api/calc-products/{create.json()['id']}/expand?quantity=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["quantity"] == 6


@pytest.mark.asyncio
async def test_create_calc_item(client):
    prod = await client.post("/api/calc-products/", json={"name": "ДляРасчета"})
    resp = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "tkp", "product_id": prod.json()["id"], "quantity": 5
    })
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 5
    assert resp.json()["product_name"] == "ДляРасчета"


@pytest.mark.asyncio
async def test_list_calc_items(client):
    prod = await client.post("/api/calc-products/", json={"name": "СписокРасчет"})
    await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "k104", "product_id": prod.json()["id"], "quantity": 1
    })
    resp = await client.get("/api/calc-items/1/k104")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_update_calc_item(client):
    prod = await client.post("/api/calc-products/", json={"name": "Обновить"})
    create = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "kso", "product_id": prod.json()["id"], "quantity": 1
    })
    resp = await client.patch(f"/api/calc-items/{create.json()['id']}", json={
        "id": create.json()["id"], "quantity": 10
    })
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 10


@pytest.mark.asyncio
async def test_delete_calc_item(client):
    prod = await client.post("/api/calc-products/", json={"name": "УдалитьПоз"})
    create = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "sho", "product_id": prod.json()["id"], "quantity": 1
    })
    resp = await client.delete(f"/api/calc-items/{create.json()['id']}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_expanded_composite(client):
    prod = await client.post("/api/calc-products/", json={
        "name": "ШкафТест", "components": [{"equipment_id": 1, "quantity": 2}]
    })
    await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "tkp", "product_id": prod.json()["id"], "quantity": 3
    })
    resp = await client.get("/api/calc-items/1/tkp/expanded")
    assert resp.status_code == 200
    expanded = resp.json()
    found = [e for e in expanded if e["product_name"] == "ШкафТест"]
    assert len(found) == 1
    assert found[0]["quantity"] == 6
