from scr.constants import SETTING_CONTRACT_FOLDER
from scr.dbase import crud_settings
from scr.dbase.crud_contract_specs import folder_safe_name
from scr.dbase.models import Directors, Organization, Positions


async def _company(s) -> int:
    pos = Positions(name="Folder position")
    s.add(pos)
    await s.flush()
    director = Directors(name="Folder Director", position_id=pos.id)
    s.add(director)
    await s.flush()
    org = Organization(name='ООО "Ромашка: Юг"', director_id=director.id)
    s.add(org)
    await s.commit()
    return org.id


def test_folder_safe_name():
    assert folder_safe_name('ООО "Ромашка: Юг"') == "ООО_Ромашка_Юг"
    assert folder_safe_name('"/"') == "Unknown"


async def test_contract_folder(client, db_session, tmp_path):
    company_id = await _company(db_session)

    # Без настройки — понятная ошибка
    resp = await client.post("/reg/api/contract-specs/", json={"company_id": company_id, "new_contract": True})
    spec = resp.json()
    resp = await client.post(f"/reg/api/contract-specs/{spec['id']}/folder")
    assert resp.status_code == 400

    await crud_settings.set_setting(db_session, SETTING_CONTRACT_FOLDER, str(tmp_path))
    await db_session.commit()

    # Новый договор — папка {номер}_{организация} создаётся сразу
    resp = await client.post("/reg/api/contract-specs/", json={"company_id": company_id, "new_contract": True})
    first = resp.json()
    folder = tmp_path / f"{first['contract_number']}_ООО_Ромашка_Юг"
    assert folder.is_dir()

    # Вторая спецификация того же договора — та же папка
    resp = await client.post(
        "/reg/api/contract-specs/",
        json={"company_id": company_id, "contract_number": first["contract_number"], "new_contract": False},
    )
    second = resp.json()
    assert second["specification_number"] == 2
    resp = await client.post(f"/reg/api/contract-specs/{second['id']}/folder")
    assert resp.status_code == 200
    assert resp.json() == {"path": str(tmp_path) + "/" + folder.name, "created": True}
