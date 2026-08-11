import bcrypt
from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import User
from scr.dbase.schemas.schemas import UserCreate


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
