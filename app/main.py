import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, engine, get_db
from app.elasticsearch import (
    close_es_client,
    delete_from_elastic,
    init_es_index,
    search_in_elastic,
)
from app.logger import setup_logging
from app.models import Document
from app.schemas import DocumentResponse

setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск приложения: инициализация инфраструктуры...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await init_es_index()
        logger.info("Инфраструктура базы данных и Elasticsearch успешно подготовлена.")
        yield
    except Exception as e:
        logger.critical(f"Критическая ошибка при старте приложения: {e}", exc_info=True)
        raise
    finally:
        logger.info("Остановка приложения: закрытие ресурсов...")
        await close_es_client()
        await engine.dispose()
        logger.info("Все соединения успешно закрыты.")


app = FastAPI(title="Текстовый поисковик", version="1.0.0", lifespan=lifespan)


@app.get("/docs.json", include_in_schema=False)
async def get_openapi_json():
    return app.openapi()


@app.get("/search", response_model=list[DocumentResponse])
async def search_documents(
    q: str = Query(..., description="Текстовый поисковый запрос"),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Получен поисковый запрос q='{q}'")
    try:
        elastic_results = await search_in_elastic(q)
    except RuntimeError as e:
        logger.error(f"Сбой инфраструктуры поиска при обработке запроса '{q}'")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Поисковый сервис временно недоступен. Попробуйте позже.",
        ) from e

    if not elastic_results:
        logger.info(f"По запросу '{q}' ничего не найдено в Elasticsearch.")
        return []

    matched_ids = list(elastic_results.keys())
    logger.info(
        f"Elasticsearch вернул {len(matched_ids)} совпадений для запроса '{q}'. "
        " Извлекаем данные из БД..."
    )
    stmt = (
        select(Document).where(Document.id.in_(matched_ids)).order_by(Document.created_date.desc())
    )
    result = await db.execute(stmt)
    result = result.scalars().all()
    logger.info(f"Успешно сформирован ответ поиска. Возвращено {len(result)} документов.")
    return result


@app.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int = Path(..., gt=0, le=2147483647, description="ID документа"),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Получен запрос на удаление документа ID: {doc_id}")
    stmt = select(Document).where(Document.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc:
        logger.warning(f"Документ с ID {doc_id} не найден в базе данных для удаления.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")

    try:
        await db.execute(delete(Document).where(Document.id == doc_id))
        await delete_from_elastic(doc_id)
        await db.commit()
        logger.info(f"Документ ID {doc_id} успешно удален из PostgreSQL и Elasticsearch.")
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка транзакции при удалении документа {doc_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления транзакции: {e}",
        ) from e

    return Response(status_code=status.HTTP_204_NO_CONTENT)
