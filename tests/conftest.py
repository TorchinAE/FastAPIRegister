import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from scr.dbase.database import Base
from main import app
from scr.dbase.database import (
    create_db_and_tables,
)  # замените на ваш способ получения сессии

# Создаём тестовую синхронную БД в памяти (для простоты)
# Если используете async SQLAlchemy — см. примечание ниже
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db?check_same_thread=False"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Замените get_async_session на вашу зависимость, если она используется в роутах
    # Если вы НЕ используете Depends(get_async_session) в роутах — эту строку можно удалить
    # app.dependency_overrides[get_async_session] = override_get_db

    with TestClient(app) as c:
        yield c
