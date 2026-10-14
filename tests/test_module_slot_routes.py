"""Обязательные строки разделов расчёта: настройка, модули по умолчанию, расчёт."""

from sqlalchemy import select

from scr.dbase.crud_module_slots import sync_hidden_slots
from scr.dbase.models import Module, RequestCalcItem

REQUEST_ID = 9001  # заявка не нужна: расчёт работает и без неё


async def _setup(client, suffix: str) -> dict:
    """Тип раздела, два типа материалов, модуль типа «A» из одного материала (цена 100)."""
    mt = (await client.post("/reg/api/module-types/", json={"name": f"Раздел {suffix}", "slug": f"sl-{suffix}"})).json()
    type_a = (await client.post("/reg/api/material-types/", json={"name": f"Выкл{suffix}"})).json()
    type_b = (await client.post("/reg/api/material-types/", json={"name": f"Шины{suffix}"})).json()
    mat = (
        await client.post("/reg/api/materials/", json={"name": f"Мат {suffix}", "price": 100, "type_id": type_a["id"]})
    ).json()
    mod = (await client.post("/reg/api/modules/", json={"name": f"Модуль {suffix}"})).json()
    await client.post(f"/reg/api/modules/{mod['id']}/items", json={"material_id": mat["id"], "quantity": 1})
    return {"mt": mt, "type_a": type_a, "type_b": type_b, "mod": mod}


async def test_module_type_filled_from_materials(client, db_session):
    ctx = await _setup(client, "t1")
    mod = await db_session.get(Module, ctx["mod"]["id"])
    assert mod.material_type_id == ctx["type_a"]["id"]


async def test_slot_crud_and_order(client):
    ctx = await _setup(client, "t2")
    url = f"/reg/api/module-types/{ctx['mt']['id']}/slots"
    first = (await client.post(url, json={"module_type_id": 0, "name": "Выключатель"})).json()
    second = (await client.post(url, json={"module_type_id": 0, "name": "Шинный мост", "hidden": True})).json()
    assert first["hidden"] is False and second["hidden"] is True
    # Повторное создание возвращает существующую строку
    again = (await client.post(url, json={"module_type_id": 0, "name": "выключатель"})).json()
    assert again["id"] == first["id"]

    resp = await client.patch(
        f"/reg/api/module-type-slots/{first['id']}", json={"material_type_ids": [ctx["type_a"]["id"]]}
    )
    assert resp.json()["type_ids"] == [ctx["type_a"]["id"]]

    await client.post(f"/reg/api/module-type-slots/{second['id']}/move", json={"direction": -1})
    names = [s["name"] for s in (await client.get(url)).json()]
    assert names == ["Шинный мост", "Выключатель"]

    assert (await client.delete(f"/reg/api/module-type-slots/{first['id']}")).status_code == 200
    assert len((await client.get(url)).json()) == 1


async def test_slot_default_checks_module_type(client):
    ctx = await _setup(client, "t3")
    slot = (
        await client.post(
            f"/reg/api/module-types/{ctx['mt']['id']}/slots",
            json={"module_type_id": 0, "name": "Шины", "material_type_ids": [ctx["type_b"]["id"]]},
        )
    ).json()
    url = f"/reg/api/module-type-slots/{slot['id']}/default"
    resp = await client.put(url, json={"module_id": ctx["mod"]["id"], "quantity": 2})
    assert resp.status_code == 400

    await client.patch(f"/reg/api/module-type-slots/{slot['id']}", json={"material_type_ids": []})
    resp = await client.put(url, json={"module_id": ctx["mod"]["id"], "quantity": 2})
    assert resp.status_code == 200
    assert resp.json()["item"]["quantity"] == 2

    resp = await client.put(url, json={"module_id": None})
    assert resp.json() == {"item": None}


async def test_calc_with_visible_and_hidden_slots(client, db_session):
    ctx = await _setup(client, "t4")
    type_id, mod_id = ctx["mt"]["id"], ctx["mod"]["id"]
    slots_url = f"/reg/api/module-types/{type_id}/slots"
    visible = (await client.post(slots_url, json={"module_type_id": 0, "name": "Видимая"})).json()
    hidden = (await client.post(slots_url, json={"module_type_id": 0, "name": "Скрытая", "hidden": True})).json()
    await client.put(f"/reg/api/module-type-slots/{hidden['id']}/default", json={"module_id": mod_id, "quantity": 3})

    block = await client.post("/reg/api/request-calcs/", json={"request_id": REQUEST_ID, "module_type_id": type_id})
    block = block.json()["block"]
    # Скрытая строка не выводится, но входит в стоимость
    assert [s["slot_id"] for s in block["slots"]] == [visible["id"]]
    assert block["slots"][0]["item"] is None
    assert block["hidden_total"] == 300
    assert block["total_cost"] == 300

    calc_id = block["id"]
    resp = await client.put(f"/reg/api/request-calcs/{calc_id}/slots/{hidden['id']}", json={"module_id": mod_id})
    assert resp.status_code == 400
    resp = await client.put(
        f"/reg/api/request-calcs/{calc_id}/slots/{visible['id']}", json={"module_id": mod_id, "quantity": 1}
    )
    assert resp.json()["item"]["module_id"] == mod_id
    # Тот же модуль можно добавить в блок и отдельной строкой
    resp = await client.post(f"/reg/api/request-calcs/{calc_id}/items", json={"calc_id": calc_id, "module_id": mod_id})
    assert resp.status_code == 200

    # Скрытая строка всегда как в «по умолчанию»
    await client.put(f"/reg/api/module-type-slots/{hidden['id']}/default", json={"module_id": mod_id, "quantity": 5})
    assert await sync_hidden_slots(db_session, REQUEST_ID)
    await db_session.commit()
    stmt = select(RequestCalcItem).where(RequestCalcItem.calc_id == calc_id, RequestCalcItem.slot_id == hidden["id"])
    assert (await db_session.execute(stmt)).scalar_one().quantity == 5

    # Удалённая строка — модуль остаётся в расчёте обычной строкой
    await client.delete(f"/reg/api/module-type-slots/{visible['id']}")
    stmt = select(RequestCalcItem).where(RequestCalcItem.calc_id == calc_id, RequestCalcItem.slot_id.is_(None))
    assert len((await db_session.execute(stmt)).scalars().all()) == 2


def _js(text: str) -> str:
    """Строка так, как её выводит фильтр tojson (кириллица экранируется)."""
    import json

    return json.dumps(text)[1:-1]


async def test_pages_render_slots(client, db_session):
    from scr.dbase.models import Request, User

    ctx = await _setup(client, "t5")
    type_id, mod_id = ctx["mt"]["id"], ctx["mod"]["id"]
    slots_url = f"/reg/api/module-types/{type_id}/slots"
    slot = (await client.post(slots_url, json={"module_type_id": 0, "name": "Ячейка-строка"})).json()
    await client.post(slots_url, json={"module_type_id": 0, "name": "Скрытая-строка", "hidden": True})
    await client.put(f"/reg/api/module-type-slots/{slot['id']}/default", json={"module_id": mod_id})

    user = User(name="Слоты", email="slots@test.ru", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    req = Request(manager_id=user.id)
    db_session.add(req)
    await db_session.commit()
    client.cookies.set("user_email", "slots@test.ru")

    resp = await client.get(f"/reg/module-type-slots?type={ctx['mt']['slug']}")
    assert resp.status_code == 200 and _js("Ячейка-строка") in resp.text
    resp = await client.get(f"/reg/module-types-calc/{type_id}/defaults")
    assert resp.status_code == 200 and _js("Скрытая-строка") in resp.text
    resp = await client.get(f"/reg/modules/{mod_id}")
    assert resp.status_code == 200 and "Тип модуля" in resp.text
    resp = await client.get(f"/reg/requests/{req.id}/calc/{ctx['mt']['slug']}")
    assert resp.status_code == 200
    assert _js("Ячейка-строка") in resp.text and _js("Скрытая-строка") not in resp.text
    resp = await client.get(f"/reg/api/requests/{req.id}/kit/export-excel")
    assert resp.status_code == 200
