from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.skill import UserSkill
from app.services.auth import get_current_user
from pydantic import BaseModel


class SkillIn(BaseModel):
    name: str
    icon: str = ''
    description: str = ''
    prompt: str = ''
    tools: list = []
    category: str = 'custom'


class SkillOut(BaseModel):
    id: int
    name: str
    icon: str
    description: str
    prompt: str
    tools: list
    category: str

    class Config:
        from_attributes = True


router = APIRouter()


@router.get('/skills', response_model=list[SkillOut])
async def list_skills(user=Depends(get_current_user), db=Depends(get_db)):
    r = await db.execute(select(UserSkill).where(UserSkill.user_id == user.id))
    return [SkillOut.model_validate(s) for s in r.scalars()]


@router.post('/skills', response_model=SkillOut)
async def create_skill(req: SkillIn, user=Depends(get_current_user), db=Depends(get_db)):
    s = UserSkill(user_id=user.id, **req.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return SkillOut.model_validate(s)


@router.delete('/skills/{skill_id}')
async def delete_skill(skill_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    r = await db.execute(select(UserSkill).where(UserSkill.id == skill_id, UserSkill.user_id == user.id))
    s = r.scalar_one_or_none()
    if s:
        await db.delete(s); await db.commit()
    return {'ok': True}
