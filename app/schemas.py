from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: int
    text: str
    rubrics: list[str] | None
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)
