import logging

from elasticsearch import AsyncElasticsearch, TransportError

from app.config import settings

logger = logging.getLogger(__name__)

es_client = AsyncElasticsearch(
    hosts=[settings.ELASTICSEARCH_URL], request_timeout=settings.ES_TIMEOUT
)


async def close_es_client() -> None:
    await es_client.close()


async def init_es_index():
    exists = await es_client.indices.exists(index=settings.ES_INDEX_NAME)
    if not exists:
        await es_client.indices.create(
            index=settings.ES_INDEX_NAME,
            body={
                "mappings": {
                    "properties": {
                        "id": {"type": "integer"},
                        "created_date": {"type": "date"},
                        "text": {"type": "text", "analyzer": "russian"},
                    }
                }
            },
        )


async def index_document(doc_id: int, text: str, created_date: str):
    await es_client.index(
        index=settings.ES_INDEX_NAME,
        id=str(doc_id),
        body={"id": doc_id, "text": text, "created_date": created_date},
    )


async def delete_from_elastic(doc_id: int):
    try:
        await es_client.delete(index=settings.ES_INDEX_NAME, id=str(doc_id))
    except Exception as e:
        logger.warning(
            f"Не удалось удалить документ {doc_id} из Elastic (возможно, уже удален): {e}"
        )


async def search_in_elastic(query_text: str) -> dict[int, list[str]]:
    if not query_text.strip():
        return {}

    try:
        response = await es_client.search(
            index=settings.ES_INDEX_NAME,
            body={
                "query": {"match": {"text": query_text}},
                "sort": [{"created_date": {"order": "desc"}}, "_score"],
                "highlight": {
                    "fields": {"text": {"fragment_size": 150, "number_of_fragments": 3}}
                },
                "_source": False,
                "size": 20,
            },
        )

        return {
            int(hit["_id"]): hit.get("highlight", {}).get("text", [])
            for hit in response["hits"]["hits"]
        }
    except (TransportError, Exception) as e:
        logger.error(f"Elasticsearch прервал работу или недоступен: {e}", exc_info=True)
        raise RuntimeError("Search infrastructure failure") from e
