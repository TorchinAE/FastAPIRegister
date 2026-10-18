import pytest

from scr.dbase.crud_modules import nom_tok_from_name
from scr.dbase.models import MaterialType


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Выключатель ВВ/TEL 1000A", 1000),
        ("ВА47-29 3P 16 А", 16),  # русская «А», через пробел
        ("Рубильник 630а", 630),
        ("ТПЛ-10 200/5 0,5S/10P", None),
        ("Выключатель 20кА", None),  # кА — ток отключения, не номинальный
        ("Шина АД31", None),
        ("Предохранитель 1,5A", None),
        ("Разъединитель 9000A", None),  # вне диапазона
    ],
)
def test_nom_tok_from_name(name, expected):
    assert nom_tok_from_name(name) == expected


async def _module(client, name: str) -> dict:
    items = (await client.get(f"/reg/api/modules/?search={name}&per_page=100")).json()["items"]
    return next(m for m in items if m["name"] == name)


async def test_module_from_material_takes_type_and_current(client, db_session):
    mt = MaterialType(name="ТипИзМатериала")
    db_session.add(mt)
    await db_session.commit()
    mat = (
        await client.post("/reg/api/materials/", json={"name": "МодИзМат 1250A", "price": 5, "type_id": mt.id})
    ).json()
    resp = await client.post(f"/reg/api/materials/{mat['id']}/toggle-module")
    assert resp.json()["action"] == "created"
    mod = await _module(client, "МодИзМат 1250A")
    assert mod["material_type_id"] == mt.id
    assert mod["nom_tok"] == 1250 and mod["nom_tok_manual"] is True


async def test_bulk_module_without_current_in_name(client, db_session):
    mat = (await client.post("/reg/api/materials/", json={"name": "МодБезТока", "price": 5, "nom_tok": 400})).json()
    await client.post("/reg/api/materials/modules-bulk?create=true", json={"ids": [mat["id"]]})
    mod = await _module(client, "МодБезТока")
    assert mod["material_type_id"] is None
    # Тока в названии нет — ток как у материала, не ручной
    assert mod["nom_tok"] == 400 and mod["nom_tok_manual"] is False
