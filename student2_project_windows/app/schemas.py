"""Request and response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_type: str = Field(min_length=1, max_length=50, examples=["customer_phone"])
    value: str = Field(min_length=1, max_length=10000, examples=["0901234567"])


class RecordCreated(BaseModel):
    id: uuid.UUID
    record_type: str
    status: str
    created_at: datetime


class RecordRead(BaseModel):
    id: uuid.UUID
    record_type: str
    value: str
    created_at: datetime


class RecordMetadata(BaseModel):
    id: uuid.UUID
    record_type: str
    ciphertext_bytes: int
    kek_name: str
    kek_version: int | None
    created_at: datetime
    updated_at: datetime
