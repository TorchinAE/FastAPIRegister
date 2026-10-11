import io

from openpyxl import Workbook

from scr.dbase.models import (
    Directors,
    Material,
    Module,
    ModuleItem,
    ModuleType,
    ModuleTypeDefault,
    Organization,
    Positions,
    Request,
    User,
)


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return {"file": ("f.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


async def _setup(s):
    """Заявка, материал 100 ₽ / 630 А, подмодуль (2 материала) и модуль (3 подмодуля) — 600 ₽."""
    user = User(name="Calc", email="calc@test.ru", hashed_password="x")
    pos = Positions(name="Calc position")
    s.add_all([user, pos])
    await s.flush()
    director = Directors(name="Calc Director", position_id=pos.id)
    s.add(director)
    await s.flush()
    org = Organization(name="Calc Org", director_id=director.id, profitability=10)
    s.add(org)
    await s.flush()
    req = Request(manager_id=user.id, company_id=org.id)
    mat = Material(name="CalcMat", price=100, nom_tok=630, code_1c="CALC-1C")
    sub = Module(name="CalcSub")
    top = Module(name="CalcTop")
    mt = ModuleType(name="Calc KSO", slug="calc-kso")
    s.add_all([req, mat, sub, top, mt])
    await s.flush()
    s.add_all(
        [
            ModuleItem(module_id=sub.id, material_id=mat.id, quantity=2),
            ModuleItem(module_id=top.id, sub_module_id=sub.id, quantity=3),
            ModuleTypeDefault(module_type_id=mt.id, module_id=top.id, quantity=1),
        ]
    )
    await s.commit()
    return {"req": req.id, "mat": mat.id, "sub": sub.id, "top": top.id, "mt": mt.id}


async def test_calc_blocks_prices_and_section_cost(client, db_session):
    ids = await _setup(db_session)

    # Новый блок: модули по умолчанию с ценой с учётом подмодулей, рентабельность организации
    resp = await client.post("/reg/api/request-calcs/", json={"request_id": ids["req"], "module_type_id": ids["mt"]})
    assert resp.status_code == 200
    block = resp.json()["block"]
    assert block["items"][0]["module_price"] == 600.0
    assert block["profitability_percent"] == 10.0
    assert block["final_price"] == 660.0

    # Добавленный модуль сразу возвращается с ценой
    calc_id = block["id"]
    resp = await client.post(
        f"/reg/api/request-calcs/{calc_id}/items", json={"calc_id": calc_id, "module_id": ids["sub"], "quantity": 1}
    )
    assert resp.json()["module_price"] == 200.0

    # Второй блок с количеством: стоимость раздела = сумма(общая стоимость × кол-во)
    resp = await client.post("/reg/api/request-calcs/", json={"request_id": ids["req"], "module_type_id": ids["mt"]})
    second = resp.json()["block"]["id"]
    resp = await client.put(
        f"/reg/api/request-calcs/{second}", json={"id": second, "final_price": 1000, "total_cost": 900, "quantity": 3}
    )
    assert resp.status_code == 200
    resp = await client.delete(f"/reg/api/request-calcs/{second}")
    assert resp.json()["section_cost"] == 660.0


async def test_module_import_excel_and_nom_tok(client, db_session):
    ids = await _setup_module_only(db_session)
    files = _xlsx(
        [
            ["Название", "Цена за ед.", "Кол-во", "Тип материала", "Код 1С"],
            ["другое имя", 1, 7, None, "IMP-1C"],
            ["Импорт новый", 55.5, 2, None, None],
        ]
    )
    resp = await client.post(f"/reg/api/modules/{ids['mod']}/import-excel", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert (data["added"], data["created_materials"]) == (2, 1)

    resp = await client.get(f"/reg/api/modules/{ids['mod']}")
    items = {i["material"]["name"]: i for i in resp.json()["items"]}
    assert items["ImpMat"]["quantity"] == 7  # найден по коду 1С
    new_mat = await client.get(f"/reg/api/materials/{items['Импорт новый']['material_id']}")
    assert new_mat.json()["type_name"] == "Производство"

    # Ном ток модуля — максимальный из материалов, можно задать вручную и вернуть авто
    modules = {m["id"]: m for m in (await client.get("/reg/api/modules/all")).json()}
    assert modules[ids["mod"]]["nom_tok"] == 1600
    await client.patch("/reg/api/modules/", json={"id": ids["mod"], "nom_tok": 400})
    modules = {m["id"]: m for m in (await client.get("/reg/api/modules/all")).json()}
    assert modules[ids["mod"]]["nom_tok"] == 400
    assert modules[ids["mod"]]["nom_tok_manual"] is True
    await client.patch("/reg/api/modules/", json={"id": ids["mod"], "nom_tok_manual": False})
    modules = {m["id"]: m for m in (await client.get("/reg/api/modules/all")).json()}
    assert modules[ids["mod"]]["nom_tok"] == 1600


async def _setup_module_only(s):
    mat = Material(name="ImpMat", price=10, nom_tok=1600, code_1c="IMP-1C")
    mod = Module(name="ImpModule")
    s.add_all([mat, mod])
    await s.commit()
    return {"mat": mat.id, "mod": mod.id}
