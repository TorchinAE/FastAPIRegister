import pytest
import uuid


@pytest.mark.asyncio
async def test_update_user(client):
    uid = uuid.uuid4().hex[:8]
    user = (await client.post("/api/auth/register", json={
        "name": "Юзер Тест",
        "email": f"user_{uid}@ivn.ruelta.ru",
        "password": "pass",
        "city": "спб",
    })).json()
    resp = await client.patch(f"/api/users/{user['id']}", json={
        "id": user["id"],
        "name": "Юзер Обновлён",
        "email": user["email"],
        "city": "мск",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_update_user_not_found(client):
    resp = await client.patch("/api/users/99999", json={
        "id": 99999,
        "name": "Нет",
    })
    assert resp.status_code == 404
