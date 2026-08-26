import pytest


async def _create_equipment(client, name="ТестEq", is_composite=False):
    resp = await client.post("/api/equipment/", json={"name": name, "is_composite": is_composite})
    assert resp.status_code == 200
    return resp.json()


async def _create_request(client):
    resp = await client.post("/requests/create", follow_redirects=False)
    assert resp.status_code == 302
    # Extract request ID from redirect location
    location = resp.headers.get("location", "")
    req_id = location.split("/")[-1]
    return int(req_id)


@pytest.mark.asyncio
async def test_create_calc_item(client):
    eq = await _create_equipment(client, "CalcEq1")
    resp = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "tkp", "equipment_id": eq["id"], "quantity": 3
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity"] == 3
    assert data["calc_type"] == "tkp"
    assert data["equipment_name"] == "CalcEq1"


@pytest.mark.asyncio
async def test_list_calc_items(client):
    eq = await _create_equipment(client, "CalcEq2")
    await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "k104", "equipment_id": eq["id"], "quantity": 1
    })
    resp = await client.get("/api/calc-items/1/k104")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_update_calc_item(client):
    eq = await _create_equipment(client, "CalcEq3")
    create_resp = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "kso", "equipment_id": eq["id"], "quantity": 1
    })
    item_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/calc-items/{item_id}", json={
        "id": item_id, "quantity": 5
    })
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 5


@pytest.mark.asyncio
async def test_delete_calc_item(client):
    eq = await _create_equipment(client, "CalcEq4")
    create_resp = await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "sho", "equipment_id": eq["id"], "quantity": 1
    })
    item_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/calc-items/{item_id}")
    assert resp.status_code == 200
    # Verify deleted
    resp2 = await client.get("/api/calc-items/1/sho")
    assert all(i["id"] != item_id for i in resp2.json())


@pytest.mark.asyncio
async def test_set_composition(client):
    parent = await _create_equipment(client, "Composite1", is_composite=True)
    child1 = await _create_equipment(client, "Child1")
    child2 = await _create_equipment(client, "Child2")
    resp = await client.put(f"/api/equipment/{parent['id']}/composition", json=[
        {"child_id": child1["id"], "quantity": 2},
        {"child_id": child2["id"], "quantity": 3},
    ])
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_get_composition(client):
    parent = await _create_equipment(client, "Composite2", is_composite=True)
    child = await _create_equipment(client, "Child3")
    await client.put(f"/api/equipment/{parent['id']}/composition", json=[
        {"child_id": child["id"], "quantity": 5},
    ])
    resp = await client.get(f"/api/equipment/{parent['id']}/composition")
    assert resp.status_code == 200
    comps = resp.json()
    assert len(comps) == 1
    assert comps[0]["quantity"] == 5
    assert comps[0]["child_name"] == "Child3"


@pytest.mark.asyncio
async def test_expanded_composite(client):
    parent = await _create_equipment(client, "Composite3", is_composite=True)
    child = await _create_equipment(client, "Child4")
    await client.put(f"/api/equipment/{parent['id']}/composition", json=[
        {"child_id": child["id"], "quantity": 2},
    ])
    await client.post("/api/calc-items/", json={
        "request_id": 1, "calc_type": "tkp", "equipment_id": parent["id"], "quantity": 3
    })
    resp = await client.get("/api/calc-items/1/tkp/expanded")
    assert resp.status_code == 200
    expanded = resp.json()
    # Find the component from our composite
    found = [e for e in expanded if e["parent_name"] == "Composite3"]
    assert len(found) == 1
    assert found[0]["quantity"] == 6  # 2 * 3


@pytest.mark.asyncio
async def test_equipment_filter_by_section(client):
    eq = await _create_equipment(client, "SectionEq")
    resp = await client.get("/api/equipment/?is_composite=false")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_equipment_filter_composite(client):
    await _create_equipment(client, "OnlyComposite", is_composite=True)
    resp = await client.get("/api/equipment/?is_composite=true")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
