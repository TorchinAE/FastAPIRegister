import pytest


@pytest.mark.asyncio
async def test_home(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert "login" in response.text.lower() or "вход" in response.text.lower()


@pytest.mark.asyncio
async def test_create_position(client):
    response = await client.post(
        "/api/positions/", json={"name": "Директор"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Директор"
    assert "id" in data


@pytest.mark.asyncio
async def test_read_positions(client):
    response = await client.get("/api/positions/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_add_dir(client):
    director_data = {
        "name": "Тест Иван Петрович",
        "email": "test@example.com",
        "phone": "+79991112233",
        "position_id": 1,
    }
    response = await client.post("/api/directors/", json=director_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Тест Иван Петрович"


@pytest.mark.asyncio
async def test_read_dirs(client):
    response = await client.get("/api/directors/")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
