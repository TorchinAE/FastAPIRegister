import httpx
import pytest


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "home page"}


def test_create_start(client):
    response = client.post("/create_start")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_add_dir_async():
    async with httpx.AsyncClient(base_url="http://test") as ac:
        response = await ac.post("/dir", json={...})
        assert response.status_code == 200


def test_add_dir(client):
    director_data = {
        "name": "Тест Иван",
        "short_name": "Тест И.",
        "email": "test@example.com",
        "phone": "+79991112233",
        "post_id": 1,
        "petition_id": 1,
    }
    response = client.post("/dir", json=director_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Тест Иван"
    assert "id" in data


def test_read_dir(client):
    response = client.get("/dir")
    assert response.status_code == 200
    data = response.json()
    assert "directors" in data
    assert isinstance(data["directors"], list)


def test_read_dir_item(client):
    # Сначала добавим директора
    director_data = {
        "name": "Тест для GET by ID",
        "short_name": "Тест GET",
        "email": "get@example.com",
        "phone": "+79990001122",
        "post_id": 1,
        "petition_id": 1,
    }
    create_resp = client.post("/dir", json=director_data)
    director_id = create_resp.json()["id"]

    # Теперь получим его
    response = client.get(f"/dir/{director_id}")
    assert response.status_code == 200
    assert response.json()["id"] == director_id


def test_update_dir(client):
    # Создаём
    director_data = {
        "name": "Для патча",
        "short_name": "Старый",
        "email": "patch_old@example.com",
        "phone": "+79991110000",
        "post_id": 1,
        "petition_id": 1,
    }
    create_resp = client.post("/dir", json=director_data)
    director_id = create_resp.json()["id"]

    # Патчим
    update_data = {"short_name": "Новый", "phone": "+79992223344"}
    response = client.patch(f"/dir/{director_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["short_name"] == "Новый"
    assert response.json()["phone"] == "+79992223344"


def test_del_dir(client):
    # Создаём
    director_data = {
        "name": "На удаление",
        "short_name": "Удалить",
        "email": "del@example.com",
        "phone": "+79995556677",
        "post_id": 1,
        "petition_id": 1,
    }
    create_resp = client.post("/dir", json=director_data)
    director_id = create_resp.json()["id"]

    # Удаляем
    response = client.delete(f"/dir/{director_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Директор удален."

    # Проверяем, что его больше нет
    get_resp = client.get(f"/dir/{director_id}")
    assert get_resp.status_code == 404
