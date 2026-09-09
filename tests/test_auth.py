import pytest


@pytest.mark.asyncio
async def test_register_user(client):
    resp = await client.post("/api/auth/register", json={
        "name": "Тест Тест Тестович",
        "email": "test_auth@ivn.ruelta.ru",
        "password": "secret123",
        "city": "мск",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test_auth@ivn.ruelta.ru"
    assert data["name"] == "Тест Тест Тестович"
    assert "user_email" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post("/api/auth/register", json={
        "name": "Первый",
        "email": "dup@ivn.ruelta.ru",
        "password": "pass1",
    })
    resp = await client.post("/api/auth/register", json={
        "name": "Второй",
        "email": "dup@ivn.ruelta.ru",
        "password": "pass2",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/auth/register", json={
        "name": "Логин Тест",
        "email": "login@ivn.ruelta.ru",
        "password": "mypass",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "login@ivn.ruelta.ru",
        "password": "mypass",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "login@ivn.ruelta.ru"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "name": "Неверный",
        "email": "wrong@ivn.ruelta.ru",
        "password": "correct",
    })
    resp = await client.post("/api/auth/login", json={
        "email": "wrong@ivn.ruelta.ru",
        "password": "incorrect",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout(client):
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Выход выполнен"


@pytest.mark.asyncio
async def test_me_authenticated(client):
    await client.post("/api/auth/register", json={
        "name": "Ме Тест",
        "email": "me@ivn.ruelta.ru",
        "password": "pass",
    })
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@ivn.ruelta.ru"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_non_ivn_domain(client):
    resp = await client.post("/api/auth/register", json={
        "name": "Чужой",
        "email": "outsider@gmail.com",
        "password": "secret123",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_allows_ivn_domain(client):
    resp = await client.post("/api/auth/register", json={
        "name": "Свой",
        "email": "svoi@ivn.ruelta.ru",
        "password": "secret123",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "svoi@ivn.ruelta.ru"
