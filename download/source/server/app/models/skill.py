from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey, func
from app.database import Base


class UserSkill(Base):
    __tablename__ = 'user_skills'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(10), default='')
    description = Column(Text, default='')
    prompt = Column(Text, default='')
    tools = Column(JSON, default=list)
    category = Column(String(50), default='custom')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
