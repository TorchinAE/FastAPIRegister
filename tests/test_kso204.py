import io
import zipfile

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select

from scr.dbase import crud_kso204
from scr.dbase.models import (
    Counterparty,
    Directors,
    Material,
    MaterialType,
    Module,
    ModuleItem,
    ModuleType,
    ModuleTypeDefault,
    ModuleTypeSlot,
    Organization,
    Positions,
    Request,
    RequestCalc,
    User,
)
from scr.utils import kso204
from scr.utils.xlsx_patch import XlsxPatcher, set_cells


@pytest.fixture
def tkp_root(tmp_path, monkeypatch):
    """Файлы вариантов — во временной папке (adres_server в тестах не задан)."""
    monkeypatch.setattr(crud_kso204, "LOCAL_TKP_ROOT", tmp_path)
    return tmp_path


async def _setup(s):
    user = User(name="Kso", email="kso@test.ru", hashed_password="x")
    pos = Positions(name="Kso position")
    s.add_all([user, pos])
    await s.flush()
    director = Directors(name="Kso Director", position_id=pos.id)
    s.add(director)
    await s.flush()
    org = Organization(name="Kso Org", director_id=director.id, profitability=15)
    s.add(org)
    await s.flush()
    cp = Counterparty(name="Петров Пётр", email="kso-cp@test.ru", phone="8-900-000-00-00", company_id=org.id)
    s.add(cp)
    await s.flush()
    req = Request(manager_id=user.id, company_id=org.id, counterparty_id=cp.id, description="ПС Тестовая")
    mt = (await s.execute(select(ModuleType).where(ModuleType.slug == "kso"))).scalar_one_or_none()
    if mt:
        # Раздел «kso» мог создать другой тест — начинаем с чистых строк и модулей по умолчанию
        await s.execute(delete(ModuleTypeDefault).where(ModuleTypeDefault.module_type_id == mt.id))
        await s.execute(delete(ModuleTypeSlot).where(ModuleTypeSlot.module_type_id == mt.id))
    else:
        mt = ModuleType(name="КСО", slug="kso")
    mat = Material(name="KsoMat", price=100)
    bus_type = MaterialType(name="KsoШины")
    s.add_all([req, mt, mat, bus_type])
    await s.flush()
    req.tkp_num = f"{req.id}-ив"
    slots = {}
    for i, name in enumerate(("Выключатель", "Трансформатор тока", "ТН", "Прочее"), start=1):
        slots[name] = ModuleTypeSlot(module_type_id=mt.id, name=name, sort_order=i)
    # «Прочее» нет на листе КСО-204 — модуль идёт в «Дополнительно» и при загрузке возвращается в строку по типу
    slots["Прочее"].material_types = [bus_type]
    s.add_all(slots.values())
    modules = {}
    for name in ("VM12-10-20/1000", "ТПЛ-10 200/5 0,5S/10P", "НАМИТ-6", "Кронштейн", "Шинный мост"):
        modules[name] = Module(name=name, material_type_id=bus_type.id if name == "Шинный мост" else None)
    modules["VM12-10-20/1000"].nom_tok = 1000  # ток шин в опросном листе — максимальный ном. ток модулей
    s.add_all(modules.values())
    await s.flush()
    s.add_all([ModuleItem(module_id=m.id, material_id=mat.id, quantity=1) for m in modules.values()])
    await s.commit()
    return {
        "req": req.id,
        "mt": mt.id,
        "slots": {k: v.id for k, v in slots.items()},
        "mods": {k: v.id for k, v in modules.items()},
    }


async def _fill_block(client, ids, slot_modules: dict, manual: list, qty: tuple, profit: float, purpose=None):
    resp = await client.post("/reg/api/request-calcs/", json={"request_id": ids["req"], "module_type_id": ids["mt"]})
    calc_id = resp.json()["block"]["id"]
    for slot, (module, quantity) in slot_modules.items():
        resp = await client.put(
            f"/reg/api/request-calcs/{calc_id}/slots/{ids['slots'][slot]}",
            json={"module_id": ids["mods"][module], "quantity": quantity},
        )
        assert resp.status_code == 200
    for module, quantity in manual:
        await client.post(
            f"/reg/api/request-calcs/{calc_id}/items",
            json={"calc_id": calc_id, "module_id": ids["mods"][module], "quantity": quantity},
        )
    resp = await client.put(
        f"/reg/api/request-calcs/{calc_id}",
        json={"id": calc_id, "fot": 1500, "overhead": 700, "profitability_percent": profit,
              "qty_1sh": qty[0], "qty_2sh": qty[1], "purpose": purpose},
    )  # fmt: skip
    assert resp.status_code == 200
    return calc_id


async def _blocks(db_session, req_id: int, mt_id: int) -> list[dict]:
    from sqlalchemy.orm import selectinload

    from scr.dbase.models import RequestCalcItem

    stmt = (
        select(RequestCalc)
        .where(RequestCalc.request_id == req_id, RequestCalc.module_type_id == mt_id)
        .options(selectinload(RequestCalc.items).selectinload(RequestCalcItem.module))
        .order_by(RequestCalc.id)
        .execution_options(populate_existing=True)
    )
    result = []
    for c in (await db_session.execute(stmt)).scalars().all():
        result.append(
            {
                "qty": (c.qty_1sh, c.qty_2sh, c.quantity),
                "fot": float(c.fot),
                "purpose": c.purpose,
                "overhead": float(c.overhead),
                "profit": float(c.profitability_percent),
                "items": sorted((it.slot_id or 0, it.module.name, it.quantity) for it in c.items),
            }
        )
    return result


def test_set_cells_keeps_style_and_inserts_missing():
    xml = (
        '<worksheet><sheetData><row r="2"><c r="B2" s="5" t="s"><v>3</v></c><c r="D2" s="7"/></row>'
        '<row r="5"><c r="A5"><v>1</v></c></row></sheetData></worksheet>'
    )
    out = set_cells(xml, {"B2": "Текст & <знаки>", "C2": 12.5, "D2": None, "A3": 7, "C5": "x"})
    assert '<c r="B2" s="5" t="inlineStr"><is><t>Текст &amp; &lt;знаки&gt;</t></is></c>' in out
    assert '<c r="C2"><v>12.5</v></c><c r="D2" s="7"/>' in out  # вставка по порядку столбцов, стиль сохранён
    assert out.index('<row r="2"') < out.index('<row r="3">') < out.index('<row r="5"')
    assert '<c r="A5"><v>1</v></c><c r="C5" t="inlineStr">' in out


def test_kso204_template_parts_preserved():
    """Сводные, подключения, картинки остаются; цепочка вычислений удаляется, пересчёт при открытии."""
    template = kso204.TEMPLATE_PATH.read_bytes()
    data, warnings = kso204.build_kso204(kso204.KsoHeader(tkp_num="1-ив"), [kso204.KsoBlock()], template)
    assert warnings == []
    before = set(zipfile.ZipFile(io.BytesIO(template)).namelist())
    after = zipfile.ZipFile(io.BytesIO(data))
    assert before - set(after.namelist()) <= {"xl/calcChain.xml"}
    assert "xl/pivotTables/pivotTable1.xml" in after.namelist()
    assert 'fullCalcOnLoad="1"' in after.read("xl/workbook.xml").decode()
    assert XlsxPatcher(data).sheets["КСО-204"] == "xl/worksheets/sheet1.xml"


def test_split_tkp_num():
    assert kso204.split_tkp_num("8-ив") == ("8", 1, "ив")
    assert kso204.split_tkp_num("8-2ив") == ("8", 2, "ив")
    assert kso204.split_tkp_num("13442-ив") == ("13442", 1, "ив")
    assert kso204.split_tkp_num("ABC") is None
    assert kso204.variant_tkp_num("8", 3, "ив") == "8-3ив"
    assert kso204.variant_tkp_num("8", 1, "ив") == "8-ив"
    assert kso204.kso204_filename("13442-ив") == "КСО204-ткп13442-ив.xlsx"


async def test_kso204_export_and_variants(client, db_session, tkp_root):
    ids = await _setup(db_session)
    req_id = ids["req"]
    await _fill_block(
        client,
        ids,
        {"Выключатель": ("VM12-10-20/1000", 1), "Трансформатор тока": ("ТПЛ-10 200/5 0,5S/10P", 3),
         "Прочее": ("Шинный мост", 1)},
        [("Кронштейн", 2)],
        (2, 1),
        20,
        "Линия",
    )  # fmt: skip
    await _fill_block(client, ids, {"ТН": ("НАМИТ-6", 1)}, [], (0, 1), 12.5)

    # Выгрузка: ячейки опросного листа, сводной и расчёта
    resp = await client.get(f"/reg/api/requests/{req_id}/kso204/export-excel")
    assert resp.status_code == 200
    assert "%D0%9A%D0%A1%D0%9E204-%D1%82%D0%BA%D0%BF" in resp.headers["content-disposition"]  # КСО204-ткп
    wb = load_workbook(io.BytesIO(resp.content))
    kso, summary, calc = wb["КСО-204"], wb["Сводная информация"], wb["расчет"]
    assert kso["I1"].value == f"{req_id}-ив"
    assert kso["D2"].value == "ПС Тестовая" and kso["D3"].value == "Kso Org"
    assert kso["F5"].value == "Петров Пётр" and kso["K5"].value == "8-900-000-00-00"
    assert (kso["D15"].value, kso["E15"].value, kso["F15"].value) == ("Линия", "Блок 2", None)
    assert kso["D10"].value == "КСО-204" and kso["F10"].value is None
    assert kso["C12"].value == 1000
    assert kso["D18"].value == "VM12-10-20/1000"
    assert (kso["D21"].value, kso["D22"].value) == (3, "ТПЛ-10 200/5 0,5S/10P")
    assert kso["D25"].value is None and kso["E25"].value == "НАМИТ-6"
    # «Прочее» не сопоставлено со строкой листа и модули, добавленные вручную, — в «Дополнительно»
    assert [(kso[f"D{q}"].value, kso[f"D{n}"].value) for q, n in ((32, 33), (34, 35), (36, 37))] == [
        (2, "Кронштейн"),
        (1, "Шинный мост"),
        (None, None),
    ]
    assert (summary["K2"].value, summary["L2"].value) == ("1СШ", "2СШ")
    assert [summary[f"{c}3"].value for c in "CKL"] == ["=K3+L3", 2, 1]
    assert [summary[f"{c}4"].value for c in "KL"] == [0, 1]
    assert summary["C5"].value == "=K5+L5" and summary["K5"].value is None
    assert (calc["C33"].value, calc["E33"].value) == (0.2, 0.125)
    assert (calc["C42"].value, calc["C43"].value) == (700, 1500)
    assert (calc["C40"].value, calc["C41"].value) == (1.6, 0.21)  # Кнакл, Кфот из настроек (по умолчанию)
    assert calc["G33"].value is None

    blocks_before = await _blocks(db_session, req_id, ids["mt"])

    # +Вариант: файл текущего варианта сохранён, номер ТКП → следующий вариант
    resp = await client.post(f"/reg/api/requests/{req_id}/variants")
    assert resp.status_code == 200
    assert resp.json()["tkp_num"] == f"{req_id}-2ив"
    assert (tkp_root / str(req_id) / f"КСО204-ткп{req_id}-ив.xlsx").is_file()

    # Вариант 2 меняем и сохраняем при переходе к варианту 1
    stmt = select(RequestCalc.id).where(RequestCalc.request_id == req_id).order_by(RequestCalc.id)
    calcs = (await db_session.execute(stmt)).scalars().all()
    await client.delete(f"/reg/api/request-calcs/{calcs[1]}")

    resp = await client.post(f"/reg/api/requests/{req_id}/variants/1/load", json={"save_current": True})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"tkp_num": f"{req_id}-ив", "warnings": []}
    assert await _blocks(db_session, req_id, ids["mt"]) == blocks_before

    resp = await client.get(f"/reg/api/requests/{req_id}/variants")
    data = resp.json()
    assert data["current"] == 1
    assert [(v["n"], v["tkp_num"], v["saved"]) for v in data["variants"]] == [
        (1, f"{req_id}-ив", True),
        (2, f"{req_id}-2ив", True),
    ]

    # Вариант 2 сохранён с одним блоком
    resp = await client.post(f"/reg/api/requests/{req_id}/variants/2/load", json={"save_current": False})
    assert resp.status_code == 200
    blocks = await _blocks(db_session, req_id, ids["mt"])
    assert len(blocks) == 1 and blocks[0] == blocks_before[0]
    assert (await db_session.get(Request, req_id, populate_existing=True)).tkp_num == f"{req_id}-2ив"

    resp = await client.post(f"/reg/api/requests/{req_id}/variants/5/load", json={"save_current": False})
    assert resp.status_code == 404
