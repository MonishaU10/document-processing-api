
from pydantic import BaseModel, Field


class DocumentUpdate(BaseModel):
    filename: str | None = Field(
        default=None,
        min_length=1,
        max_length=255
    )
