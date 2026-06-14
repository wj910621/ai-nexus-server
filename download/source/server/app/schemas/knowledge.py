from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class DocumentCreate(BaseModel):
    title: str = Field(..., max_length=200)
    content: str
    category: str = 'general'


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    id: int
    title: str
    content: str
    score: float = 0.0
