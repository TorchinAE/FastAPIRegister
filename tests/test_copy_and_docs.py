"""Копирование блоков и шаблонов, заполнение пустого блока из шаблона, договор и спецификация в Word,
выгрузка модулей по фильтру, адрес доставки в ТКП, подбор модуля без типа по материалам."""

import io

from docx import Document
from openpyxl import load_workbook

from scr.dbase import crud_module_types
from scr.dbase.crud_module_slots import allowed_module
from scr.dbase.models import (
    Delivery,
    Directors,
    Material,
    MaterialType,
    Module,
    ModuleItem,
    ModuleType,
    ModuleTypeDefault,
    ModuleTypeSlot,
    ModuleTypeTemplate,
    Organization,
    PaymentItem,
    Positions,
    Request,
    User,
)


async def _setup(s, sfx: str, slug: str):
    user = User(name=f"Cp{sfx}", email=f"cp{sfx}@test.ru", hashed_password="x")
    pos = Positions(name=f"Генеральный директор {sfx}")
    s.add_all([user, pos])
    await s.flush()
    director = Directors(name=f"Иванов{sfx} Иван Иванович", position_id=pos.id)
    s.add(director)
    await s.flush()
    org = Organization(name=f"ООО Копия {sfx}", director_id=director.id, profitability=10)
    s.add(org)
    await s.flush()
    req = Request(manager_id=user.id, company_id=org.id)
    mt = ModuleType(name=f"Раздел {sfx}", slug=slug)
    mat = Material(name=f"CpMat{sfx}", price=100)
    mod = Module(name=f"CpMod{sfx}")
    s.add_all([req, mt, mat, mod])
    await s.flush()
    slot = ModuleTypeSlot(module_type_id=mt.id, name="Строка", sort_order=1)
    s.add_all([slot, ModuleItem(module_id=mod.id, material_id=mat.id, quantity=1)])
    await s.flush()
    tpl = ModuleTypeTemplate(module_type_id=mt.id, name="Основной", sort_order=1)
    s.add(tpl)
    await s.commit()
    return {"req": req.id, "mt": mt.id, "mod": mod.id, "slot": slot.id, "tpl": tpl.id, "org": org.id}


async def test_copy_block_next_to_source(client, db_session):
    ids = await _setup(db_session, "a", "kru")
    first = (
        await client.post("/reg/api/request-calcs/", json={"request_id": ids["req"], "module_type_id": ids["mt"]})
    ).json()["block"]
    second = (
        await client.post("/reg/api/request-calcs/", json={"request_id": ids["req"], "module_type_id": ids["mt"]})
    ).json()["block"]
    await client.put(
        f"/reg/api/request-calcs/{first['id']}/slots/{ids['slot']}", json={"module_id": ids["mod"], "quantity": 2}
    )
    await client.put(
        f"/reg/api/request-calcs/{first['id']}", json={"id": first["id"], "name": "Ввод-1", "quantity": 3, "fot": 7}
    )

    resp = await client.post(f"/reg/api/request-calcs/{first['id']}/copy")
    assert resp.status_code == 200
    copy = resp.json()["block"]
    assert copy["id"] not in (first["id"], second["id"])
    assert copy["name"] == "Ввод-1"
    assert copy["quantity"] == 3
    assert copy["slots"][0]["item"]["module_id"] == ids["mod"]
    assert copy["slots"][0]["item"]["quantity"] == 2

    # Порядок раздела: исходный, копия, второй
    calcs = await crud_module_types.get_calcs(db_session, ids["req"], ids["mt"])
    assert [c.id for c in calcs] == [first["id"], copy["id"], second["id"]]

    assert (await client.post("/reg/api/request-calcs/999999/copy")).status_code == 404


async def test_copy_template_next_to_source(client, db_session):
    ids = await _setup(db_session, "b", "tpl-copy-b")
    db_session.add(
        ModuleTypeDefault(module_type_id=ids["mt"], module_id=ids["mod"], quantity=1, template_id=ids["tpl"])
    )
    await db_session.commit()
    other = (await client.post(f"/reg/api/module-types/{ids['mt']}/templates", json={"name": "Второй"})).json()

    resp = await client.post(f"/reg/api/module-type-templates/{ids['tpl']}/copy")
    assert resp.status_code == 200
    copy = resp.json()
    assert copy["name"] == "Основной (копия)"
    assert [it["module_id"] for it in copy["items"]] == [ids["mod"]]
    tpls = (await client.get(f"/reg/api/module-types/{ids['mt']}/templates")).json()
    assert [t["id"] for t in tpls] == [ids["tpl"], copy["id"], other["id"]]


async def test_empty_single_block_filled_from_template(client, db_session):
    ids = await _setup(db_session, "c", "ktp-c")
    # Блок создан, когда шаблон был пуст
    calcs = await crud_module_types.get_or_create_calcs(db_session, ids["req"], ids["mt"])
    await db_session.commit()
    assert not calcs[0].items

    db_session.add(
        ModuleTypeDefault(
            module_type_id=ids["mt"], module_id=ids["mod"], quantity=2, slot_id=ids["slot"], template_id=ids["tpl"]
        )
    )
    await db_session.commit()
    calcs = await crud_module_types.get_or_create_calcs(db_session, ids["req"], ids["mt"])
    await db_session.commit()
    assert [(it.module_id, it.quantity, it.slot_id) for it in calcs[0].items] == [(ids["mod"], 2, ids["slot"])]
    assert float(calcs[0].total_cost) == 200


async def test_contract_and_spec_docx(client, db_session):
    ids = await _setup(db_session, "d", "kso-d")
    db_session.add_all(
        [
            Delivery(request_id=ids["req"], address="г. Москва, ул. Тестовая, 1", final_price=1000),
            PaymentItem(request_id=ids["req"], payment_type="аванс", percent=50),
            PaymentItem(request_id=ids["req"], payment_type="окончательная", percent=50),
        ]
    )
    await db_session.commit()
    spec = (
        await client.post(
            "/reg/api/contract-specs/", json={"company_id": ids["org"], "request_id": ids["req"], "new_contract": True}
        )
    ).json()

    resp = await client.get(f"/reg/api/contract-specs/{spec['id']}/contract-docx")
    assert resp.status_code == 200
    text = "\n".join(p.text for p in Document(io.BytesIO(resp.content)).paragraphs)
    assert f"№{spec['contract_number']}" in text
    assert "генерального директора" in text
    assert "{" not in text

    resp = await client.get(f"/reg/api/contract-specs/{spec['id']}/spec-docx")
    assert resp.status_code == 200
    doc = Document(io.BytesIO(resp.content))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "г. Москва, ул. Тестовая, 1" in text
    assert "Самовывоз" not in text
    table_text = "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Доставка: г. Москва" in table_text

    assert (await client.get("/reg/api/contract-specs/999999/spec-docx")).status_code == 404


async def test_delivery_address_in_tkp(client, db_session):
    ids = await _setup(db_session, "e", "kso-e")
    db_session.add(
        Delivery(request_id=ids["req"], address="Казань", cost_per_truck=500, trucks_count=1, final_price=600)
    )
    await db_session.commit()
    from scr.dbase.crud_tkp import build_tkp_kit, build_tkp_summary

    req = await db_session.get(Request, ids["req"])
    summary = await build_tkp_summary(db_session, req)
    assert "Доставка: Казань" in [r["name"] for r in summary["rows"]]
    kit = await build_tkp_kit(db_session, req)
    assert kit[-1]["blocks"][0]["title"] == "Доставка: Казань"


async def test_modules_export_filtered(client, db_session):
    ids = await _setup(db_session, "f", "exp-f")
    other = Module(name="CpOther-f")
    db_session.add(other)
    await db_session.commit()
    resp = await client.post("/reg/api/modules/export-excel", json={"ids": [ids["mod"]]})
    assert resp.status_code == 200
    ws = load_workbook(io.BytesIO(resp.content))["Модули"]
    names = [row[1] for row in ws.iter_rows(min_row=2, values_only=True)]
    assert names == ["CpModf"]


async def test_untyped_module_fits_slot_by_material_types(db_session):
    dekraft = MaterialType(name="Dekraft-t")
    db_session.add(dekraft)
    await db_session.flush()
    slot = ModuleTypeSlot(module_type_id=1, name="Автомат", sort_order=1)
    slot.material_types = [dekraft]
    untyped = Module(name="Автомат без типа")
    typed_other = Module(name="Автомат другого типа", material_type_id=dekraft.id + 1000)
    assert allowed_module(slot, untyped, {dekraft.id})
    assert not allowed_module(slot, untyped, set())
    assert not allowed_module(slot, typed_other, {dekraft.id})


async def test_empty_block_with_hidden_slot_filled_from_template(db_session):
    """Скрытая строка заполняется раньше (sync_hidden_slots) — блок всё равно пустой и берёт остальное из шаблона."""
    from scr.dbase.crud_module_slots import sync_hidden_slots

    ids = await _setup(db_session, "g", "pus-g")
    hidden = ModuleTypeSlot(module_type_id=ids["mt"], name="Корпус", sort_order=2, hidden=True)
    db_session.add(hidden)
    await db_session.commit()
    calcs = await crud_module_types.get_or_create_calcs(db_session, ids["req"], ids["mt"])
    await db_session.commit()
    assert not calcs[0].items

    db_session.add_all(
        [
            ModuleTypeDefault(
                module_type_id=ids["mt"], module_id=ids["mod"], quantity=1, slot_id=ids["slot"], template_id=ids["tpl"]
            ),
            ModuleTypeDefault(
                module_type_id=ids["mt"], module_id=ids["mod"], quantity=3, slot_id=hidden.id, template_id=ids["tpl"]
            ),
        ]
    )
    await db_session.commit()
    # Как на странице расчёта: сначала скрытые строки, потом блоки
    await sync_hidden_slots(db_session, ids["req"])
    calcs = await crud_module_types.get_or_create_calcs(db_session, ids["req"], ids["mt"])
    await db_session.commit()
    got = sorted((it.slot_id, it.quantity) for it in calcs[0].items)
    assert got == sorted([(ids["slot"], 1), (hidden.id, 3)])
    assert float(calcs[0].total_cost) == 400


async def test_module_attrs_keep_decimal_comma(db_session):
    """Класс точности «0,5/10P» не режется по запятой: несколько значений — через «; »."""
    from scr.dbase import crud_modules

    mod = Module(name="ТТ запятая")
    m1 = Material(name="ТТ мат 1", price=1, accuracy_class="0,5/10P", voltage="0,4")
    m2 = Material(name="ТТ мат 2", price=1, accuracy_class="0,2S")
    db_session.add_all([mod, m1, m2])
    await db_session.flush()
    db_session.add_all(
        [
            ModuleItem(module_id=mod.id, material_id=m1.id, quantity=1),
            ModuleItem(module_id=mod.id, material_id=m2.id, quantity=1),
        ]
    )
    await db_session.commit()
    attrs = (await crud_modules.get_module_attrs(db_session))[mod.id]
    assert attrs["accuracy_class"] == "0,2S; 0,5/10P"
    assert attrs["voltage"] == "0,4"


async def test_slot_groups_share_first_slot_filters(client, db_session):
    """Строки, объединённые с предыдущей, — один блок: фильтры блока берутся у первой строки."""
    ids = await _setup(db_session, "h", "sho-h")
    mt = ids["mt"]
    db_session.add_all(
        [
            ModuleTypeSlot(module_type_id=mt, name="Автомат 2", sort_order=2),
            ModuleTypeSlot(module_type_id=mt, name="Автомат 3", sort_order=3),
            ModuleTypeSlot(module_type_id=mt, name="Корпус", sort_order=4),
        ]
    )
    await db_session.commit()
    slots = (await client.get(f"/reg/api/module-types/{mt}/slots")).json()
    first, second, third, fourth = slots
    assert (
        await client.patch(f"/reg/api/module-type-slots/{first['id']}", json={"filters": ["nom_tok"]})
    ).status_code == 200
    for s in (second, third):
        resp = await client.patch(f"/reg/api/module-type-slots/{s['id']}", json={"join_prev": True})
        assert resp.json()["join_prev"] is True

    slots = (await client.get(f"/reg/api/module-types/{mt}/slots")).json()
    assert [s["group"] for s in slots] == [first["id"]] * 3 + [fourth["id"]]
    assert [s["group_filters"] for s in slots] == [["nom_tok"]] * 3 + [[]]
