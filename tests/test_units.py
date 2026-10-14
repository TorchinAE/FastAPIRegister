async def test_material_unit_default_and_reference(client):
    # По умолчанию — «шт»
    resp = await client.post("/reg/api/materials/", json={"name": "Кабель ВВГ", "price": 10})
    assert resp.status_code == 200
    mat = resp.json()
    assert mat["unit"] == "шт"

    # Новая единица при сохранении материала попадает в справочник
    resp = await client.patch("/reg/api/materials/", json={"id": mat["id"], "unit": "пог.м."})
    assert resp.status_code == 200
    assert resp.json()["unit"] == "пог.м."
    units = {u["name"]: u["id"] for u in (await client.get("/reg/api/units/")).json()}
    assert "пог.м." in units

    # Используемую единицу удалить нельзя, неиспользуемую — можно
    assert (await client.delete(f"/reg/api/units/{units['пог.м.']}")).status_code == 400
    resp = await client.post("/reg/api/units/", json={"name": "л"})
    assert resp.status_code == 200
    assert (await client.delete(f"/reg/api/units/{resp.json()['id']}")).status_code == 200


async def test_material_accuracy_class(client):
    # По умолчанию класс точности не задан
    resp = await client.post("/reg/api/materials/", json={"name": "Трансформатор тока ТОЛ", "price": 100})
    mat = resp.json()
    assert mat["accuracy_class"] is None

    resp = await client.patch("/reg/api/materials/", json={"id": mat["id"], "accuracy_class": "0.5S"})
    assert resp.json()["accuracy_class"] == "0.5S"
    classes = {c["name"]: c["id"] for c in (await client.get("/reg/api/accuracy-classes/")).json()}
    assert "0.5S" in classes
    assert (await client.delete(f"/reg/api/accuracy-classes/{classes['0.5S']}")).status_code == 400

    # Сброс в пустое значение
    resp = await client.patch("/reg/api/materials/", json={"id": mat["id"], "accuracy_class": None})
    assert resp.json()["accuracy_class"] is None
