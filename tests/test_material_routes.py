import pytest


@pytest.mark.asyncio
async def test_create_material(client):
    response = await client.post(
        "/api/materials/", json={"name": "Резистор 100 Ом", "price": 15.50, "code_1c": "MAT001"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Резистор 100 Ом"
    assert data["price"] == 15.50
    assert data["code_1c"] == "MAT001"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_material_idempotent(client):
    await client.post("/api/materials/", json={"name": "Конденсатор", "price": 5.0})
    response = await client.post("/api/materials/", json={"name": "Конденсатор", "price": 10.0})
    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 5.0


@pytest.mark.asyncio
async def test_read_materials(client):
    await client.post("/api/materials/", json={"name": "ТестМатериал", "price": 100})
    response = await client.get("/api/materials/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_read_material_by_id(client):
    resp = await client.post("/api/materials/", json={"name": "МатериалByID", "price": 50})
    mat_id = resp.json()["id"]
    response = await client.get(f"/api/materials/{mat_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "МатериалByID"


@pytest.mark.asyncio
async def test_update_material(client):
    resp = await client.post("/api/materials/", json={"name": "ДляОбновления", "price": 10})
    mat_id = resp.json()["id"]
    response = await client.patch("/api/materials/", json={"id": mat_id, "name": "Обновлённый", "price": 20})
    assert response.status_code == 200
    assert response.json()["name"] == "Обновлённый"
    assert response.json()["price"] == 20


@pytest.mark.asyncio
async def test_delete_material(client):
    resp = await client.post("/api/materials/", json={"name": "ДляУдаления", "price": 5})
    mat_id = resp.json()["id"]
    response = await client.delete(f"/api/materials/{mat_id}")
    assert response.status_code == 200
    response = await client.get(f"/api/materials/{mat_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_read_materials_page(client):
    response = await client.get("/materials")
    # Page requires auth — expect redirect to login
    assert response.status_code in (200, 302)


@pytest.mark.asyncio
async def test_materials_pagination(client):
    for i in range(25):
        await client.post("/api/materials/", json={"name": f"PagMat{i}", "price": i})
    response = await client.get("/api/materials/?page=1&per_page=10")
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] >= 25
