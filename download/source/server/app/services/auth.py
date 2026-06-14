from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.user import User

pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')
sec = HTTPBearer()


def hash_password(pw: str) -> str: return pwd.hash(pw)
def verify_password(pw: str, h: str) -> bool: return pwd.verify(pw, h)


def create_token(uid: int) -> str:
    return jwt.encode({'sub': str(uid), 'exp': datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try: return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError: raise HTTPException(401, 'Invalid token')


async def get_current_user(cred: HTTPAuthorizationCredentials = Depends(sec), db: AsyncSession = Depends(get_db)) -> User:
    uid = int(decode_token(cred.credentials).get('sub', 0))
    u = await db.get(User, uid)
    if not u or not u.is_active: raise HTTPException(401, 'User not found')
    return u
