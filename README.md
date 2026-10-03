# Асинхронный поисковик документов

Простой поисковый сервис по текстам документов, использующий PostgreSQL для хранения метаданных и Elasticsearch для полнотекстового поиска.

## 🚀 Стек технологий

- **База данных:** PostgreSQL 16 + асинхронный драйвер `asyncpg`
- **ORM:** SQLAlchemy 2.0
- **Поисковый индекс:** Elasticsearch
- **Валидация и конфиг:** Pydantic v2 + Pydantic Settings
- **Контейнеризация:** Docker, Docker Compose

## 📂 Структура проекта

```text
search_service/
│
├── app/                        # Исходный код приложения FastAPI
│   ├── __init__.py
│   ├── config.py               # Конфигурация Pydantic
│   ├── database.py             # Настройки SQLAlchemy (engine, async_session_maker, get_db)
│   ├── elasticsearch.py        # Клиент Elasticsearch (поиск, индексация, удаление)
│   ├── logger.py               # Конфигурация структурированного логирования приложения
│   ├── models.py               # ORM-модели базы данных
│   ├── schemas.py              # Валидация входных/выходных данных (Pydantic-схемы)
│   └── main.py                 # Роутеры
│
├── scripts/                    # Вспомогательные автоматизированные скрипты
│   └── init_data.py            # Пакетный импорт данных из CSV в БД и Elastic
│
├── tests/                      # Функциональное тестирование (Pytest)
│   ├── __init__.py
│   └── test_api.py             # Асинхронные тесты с использованием Mock-объектов для Elastic
│
├── .env                        # Локальные секреты и переменные окружения
├── .env.example                # Шаблон файла конфигурации окружения
├── .gitignore                  # Список исключений для Git
├── .pre-commit-config.yaml     # Конфигурация автоматического запуска линтеров при коммите
├── Dockerfile                  # Инструкция сборки легковесного Python-контейнера приложения
├── docker-compose.yml          # Docker Compose для сервисов (FastAPI + Postgres 16 + Elastic 8.12)
├── pyproject.toml              # Централизованные настройки линтера и форматтера Ruff
├── pytest.ini                  # Конфигурация путей (PYTHONPATH) и плагинов для Pytest
├── requirements.txt            # Зафиксированные версии зависимостей проекта
└── README.md                   # Подробное руководство по развертыванию и архитектуре

```

## 🛠 Установка и запуск

### 0. Клонирование репозитория

Склонируйте репозеторий к себе на ПК

```bash
git clone https://github.com/ElliAbby/search_service.git
cd search_service
```

### 1. Настройка окружения

Скопируйте файл `.env.example` в файл `.env`

```bash
cp .env.example .env
```

Настройте переменные окружения, либо можете оставить дефолтные значения из примера.

### 2. Поднятие инфраструктуры

Запустите базу данных, Elasticsearch и само приложение через Docker Compose:

```bash
docker-compose up -d --build
```

### 3. Наполнение данными

После того как сервисы поднялись и прошли healthcheck, выполните скрипт импорта данных из posts.csv:

```bash
docker-compose exec app python -m scripts.init_data
```

## 📡 API Endpoints

Поиск документов
`GET /search?q={query}`
Возвращает до 20 документов, отсортированных по дате создания (убывание).

```bash
curl "http://localhost:8000/search?q=Мерседес"
```

Либо, если вы используете терминал, который плохо работает с русскими символами, вы можете использовать:

```bash
curl -G "http://localhost:8000/search" --data-urlencode "q=Мерседес"
```

Удаление документа
`DELETE /documents/{id}`
Удаляет документ из БД и индекса Elasticsearch.

```bash
curl -X DELETE "http://localhost:8000/documents/1"
```

## 📄 Документация (OpenAPI)

Согласно требованиям ТЗ, спецификация OpenAPI доступна по пути:

- Swagger UI: http://localhost:8000/docs
- JSON Spec (docs.json): http://localhost:8000/docs.json

## 🧪 Тестирование

Для запуска функциональных тестов (требует поднятого Docker окружения):

```bash
docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS search_db_test WITH (FORCE);" -c "CREATE DATABASE search_db_test;"
docker-compose exec app pytest tests/test_api.py -v
```

Тесты используют PostgreSQL и перед запуском должны подключаться к отдельной тестовой базе. В примере используется `search_db_test`.
