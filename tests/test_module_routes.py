import pytest


@pytest.mark.asyncio
async def test_create_module(client):
    response = await client.post("/reg/api/modules/", json={"name": "Блок питания"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Блок питания"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_module_idempotent(client):
    await client.post("/reg/api/modules/", json={"name": "ДубльМодуль"})
    response = await client.post("/reg/api/modules/", json={"name": "ДубльМодуль"})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_read_modules(client):
    await client.post("/reg/api/modules/", json={"name": "ТестМодуль"})
    response = await client.get("/reg/api/modules/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_add_material_item_to_module(client):
    mat_resp = await client.post("/reg/api/materials/", json={"name": "Резистор", "price": 10})
    mat_id = mat_resp.json()["id"]
    mod_resp = await client.post("/reg/api/modules/", json={"name": "МодульСМатериалом"})
    mod_id = mod_resp.json()["id"]
    response = await client.post(f"/reg/api/modules/{mod_id}/items", json={"material_id": mat_id, "quantity": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["material_id"] == mat_id
    assert data["quantity"] == 5


@pytest.mark.asyncio
async def test_add_submodule_item(client):
    sub_resp = await client.post("/reg/api/modules/", json={"name": "Подмодуль"})
    sub_id = sub_resp.json()["id"]
    mod_resp = await client.post("/reg/api/modules/", json={"name": "ГлавныйМодуль"})
    mod_id = mod_resp.json()["id"]
    response = await client.post(f"/reg/api/modules/{mod_id}/items", json={"sub_module_id": sub_id, "quantity": 2})
    assert response.status_code == 200
    assert response.json()["sub_module_id"] == sub_id


@pytest.mark.asyncio
async def test_module_total_price(client):
    mat_resp = await client.post("/reg/api/materials/", json={"name": "Плата", "price": 100})
    mat_id = mat_resp.json()["id"]
    mod_resp = await client.post("/reg/api/modules/", json={"name": "МодульДляЦены"})
    mod_id = mod_resp.json()["id"]
    await client.post(f"/reg/api/modules/{mod_id}/items", json={"material_id": mat_id, "quantity": 3})
    response = await client.get(f"/reg/api/modules/{mod_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_price"] == 300.0


@pytest.mark.asyncio
async def test_delete_module_item(client):
    mat_resp = await client.post("/reg/api/materials/", json={"name": "ДляУдаленияЭлемента", "price": 5})
    mat_id = mat_resp.json()["id"]
    mod_resp = await client.post("/reg/api/modules/", json={"name": "МодульДляУдаления"})
    mod_id = mod_resp.json()["id"]
    item_resp = await client.post(f"/reg/api/modules/{mod_id}/items", json={"material_id": mat_id})
    item_id = item_resp.json()["id"]
    response = await client.delete(f"/reg/api/modules/items/{item_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_module(client):
    resp = await client.post("/reg/api/modules/", json={"name": "ДляОбновления"})
    mod_id = resp.json()["id"]
    response = await client.patch("/reg/api/modules/", json={"id": mod_id, "name": "Обновлённый"})
    assert response.status_code == 200
    assert response.json()["name"] == "Обновлённый"


@pytest.mark.asyncio
async def test_delete_module(client):
    resp = await client.post("/reg/api/modules/", json={"name": "ДляУдаленияМодуль"})
    mod_id = resp.json()["id"]
    response = await client.delete(f"/reg/api/modules/{mod_id}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_read_modules_page(client):
    response = await client.get("/reg/modules")
    # Page requires auth — expect redirect to login
    assert response.status_code in (200, 302)
