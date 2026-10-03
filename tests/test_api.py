from datetime import datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Document

sync_test_url = settings.TEST_DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
sync_engine = create_engine(sync_test_url, poolclass=NullPool)


@pytest.fixture(scope="function", autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=sync_engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=sync_engine)


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    engine = create_async_engine(settings.TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine):
    maker = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def mock_search(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr("app.main.search_in_elastic", mock)
    return mock


@pytest.fixture
def mock_delete(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr("app.main.delete_from_elastic", mock)
    return mock


@pytest_asyncio.fixture
async def setup_test_data(db_session):
    docs = [
        Document(
            id=10,
            text="Купить новый Мерседес амг в автосалоне официального дилера",
            created_date=datetime(2026, 10, 1, 12, 0, 0),
            rubrics=["auto", "sales"],
        ),
        Document(
            id=20,
            text="Разработка высоконагруженных поисковых систем на Python и FastAPI",
            created_date=datetime(2026, 10, 2, 15, 30, 0),
            rubrics=["dev", "backend"],
        ),
        Document(
            id=30,
            text="Подержанный Мерседес с пробегом в отличном состоянии",
            created_date=datetime(2026, 10, 3, 9, 15, 0),
            rubrics=["auto", "used"],
        ),
    ]
    db_session.add_all(docs)
    await db_session.commit()


async def test_search_success(mock_search, setup_test_data, async_client):
    mock_search.return_value = {
        30: ["Подержанный <em>Мерседес</em> с пробегом"],
        10: ["Купить новый <em>Мерседес</em> амг"],
    }

    response = await async_client.get("/search", params={"q": "Мерседес"})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == 30
    assert data[1]["id"] == 10
    assert data[0]["rubrics"] == ["auto", "used"]


async def test_search_no_results(mock_search, async_client):
    mock_search.return_value = {}
    response = await async_client.get("/search", params={"q": "несуществующий_запрос"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


async def test_search_infrastructure_failure(mock_search, async_client):
    mock_search.side_effect = RuntimeError("Elastic is down")
    response = await async_client.get("/search", params={"q": "Мерседес"})
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"] == "Поисковый сервис временно недоступен. Попробуйте позже."


async def test_delete_document_success(mock_delete, setup_test_data, async_client, db_session):
    response = await async_client.delete("/documents/20")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    stmt = select(Document).where(Document.id == 20)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


async def test_delete_document_not_found(async_client):
    response = await async_client.delete("/documents/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Документ не найден"


async def test_delete_document_validation_error(async_client):
    response = await async_client.delete("/documents/10909439045345")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json()["detail"][0]["type"] == "less_than_equal"
