from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    DATABASE_URL: str = ""
    TEST_DATABASE_URL: str = ""

    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"
    ES_INDEX_NAME: str = "documents"
    ES_TIMEOUT: int = 5

    @model_validator(mode="after")
    def get_database_url(
        self,
    ) -> "Settings":
        # "postgresql+asyncpg://postgres:postgres@db:5432/search_db"
        base_url = f"{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}"
        self.DATABASE_URL = f"postgresql+asyncpg://{base_url}/{self.DB_NAME}"
        self.TEST_DATABASE_URL = f"postgresql+asyncpg://{base_url}/{self.DB_NAME}_test"
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
