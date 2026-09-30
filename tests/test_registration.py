from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_register_valid_domain(client):
    with patch("config.settings.MY_DOMEN", "test.ru"):
        response = await client.post(
            "/reg/api/auth/register",
            json={"name": "Тестов Тест", "email": "user@test.ru", "password": "123456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@test.ru"


@pytest.mark.asyncio
async def test_register_invalid_domain(client):
    with patch("config.settings.MY_DOMEN", "test.ru"):
        response = await client.post(
            "/reg/api/auth/register",
            json={"name": "Чужак", "email": "user@other.com", "password": "123456"},
        )
        assert response.status_code == 400
        assert "домена" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_empty_domen_allows_any(client):
    with patch("config.settings.MY_DOMEN", ""):
        response = await client.post(
            "/reg/api/auth/register",
            json={"name": "Свободный", "email": "any@anywhere.org", "password": "123456"},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "any@anywhere.org"


@pytest.mark.asyncio
async def test_register_domain_case_insensitive(client):
    with patch("config.settings.MY_DOMEN", "Test.Ru"):
        response = await client.post(
            "/reg/api/auth/register",
            json={"name": "Регистр", "email": "register@test.ru", "password": "123456"},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_register_page_shows_domain(client):
    with patch("config.settings.MY_DOMEN", "qwer.asd.ru"):
        response = await client.get("/reg/register")
        assert response.status_code == 200
        assert "qwer.asd.ru" in response.text


@pytest.mark.asyncio
async def test_register_page_submit_invalid_domain(client):
    with patch("config.settings.MY_DOMEN", "qwer.asd.ru"):
        response = await client.post(
            "/reg/register",
            data={"name": "Тест", "email": "bad@other.ru", "password": "123456"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "домена" in response.text.lower()
