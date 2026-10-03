import ast
import asyncio
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.config import settings
from app.database import async_session_maker
from app.elasticsearch import es_client, index_document, init_es_index
from app.models import Document

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "posts.csv"


async def fill_data():
    if not CSV_PATH.exists():
        print("Файл данных не найден.")
        return

    if await es_client.indices.exists(index=settings.ES_INDEX_NAME):
        await es_client.indices.delete(index=settings.ES_INDEX_NAME)
    await init_es_index()

    async with async_session_maker() as db:
        await db.execute(text("TRUNCATE TABLE documents RESTART IDENTITY CASCADE;"))
        await db.commit()

    print("Читаем CSV и запускаем чистый импорт...")
    df = pd.read_csv(CSV_PATH)
    total_rows = len(df)

    async with async_session_maker() as db:
        count = 0
        for _, row in df.iterrows():
            try:
                rubrics_list = ast.literal_eval(str(row["rubrics"]))
            except Exception:
                rubrics_list = []

            try:
                created_date = datetime.strptime(str(row["created_date"]), "%Y-%m-%d %H:%M:%S")
            except Exception:
                created_date = datetime.utcnow()

            db_doc = Document(
                text=str(row["text"]),
                created_date=created_date,
                rubrics=rubrics_list,
            )
            db.add(db_doc)
            await db.flush()

            await index_document(db_doc.id, db_doc.text, created_date.isoformat())

            count += 1
            if count % 100 == 0:
                await db.commit()
                print(f"Прогресс импорта: {count}/{total_rows} документов обработано.")

        await db.commit()
    print("Импорт успешно завершен!")


if __name__ == "__main__":
    asyncio.run(fill_data())
