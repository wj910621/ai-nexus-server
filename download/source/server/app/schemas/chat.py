from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    tokens: int = 0
    timestamp: datetime

    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    title: str = 'New Chat'
    model: str = 'deepseek-chat'
    system_prompt: str = ''
    temperature: float = 0.7
    max_tokens: int = 4096


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(ConversationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
