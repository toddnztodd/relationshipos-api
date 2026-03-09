"""Pydantic schemas for Email Threads."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmailThreadCreate(BaseModel):
    person_id: int
    subject_line: str = Field(..., max_length=500)
    first_message_date: datetime
    last_message_date: datetime
    message_count: int = Field(default=1, ge=1)
    thread_body: Optional[str] = None


class EmailThreadUpdate(BaseModel):
    subject_line: Optional[str] = Field(None, max_length=500)
    last_message_date: Optional[datetime] = None
    message_count: Optional[int] = Field(None, ge=1)
    thread_body: Optional[str] = None


class EmailThreadResponse(BaseModel):
    id: int
    user_id: int
    person_id: int
    subject_line: str
    first_message_date: datetime
    last_message_date: datetime
    message_count: int
    thread_body: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
