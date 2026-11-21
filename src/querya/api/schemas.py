from pydantic import BaseModel, Field, field_validator

from querya.db import TableDetail
from querya.tracing import RunSummary


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

    @field_validator("question")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("question is too short")
        return value


class HealthResponse(BaseModel):
    status: str
    database: str
    tables: int
    provider: str
    model: str


class SchemaResponse(BaseModel):
    dialect: str
    tables: list[TableDetail]


class RunList(BaseModel):
    items: list[RunSummary]
    total: int
