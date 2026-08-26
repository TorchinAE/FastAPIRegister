import bcrypt
from sqlalchemy import select, Result, func
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.models import User
from scr.dbase.schemas.schemas import UserCreate


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def get_users(
    session: AsyncSession, search: str | None = None, page: int = 1, per_page: int = 20
) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.id)
    count_stmt = select(func.count(User.id))
    if search:
        filter_cond = User.name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)
    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_users(session: AsyncSession) -> list[User]:
    stmt = select(User).order_by(User.name)
    result: Result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result: Result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        phone=user_in.phone,
        city=user_in.city,
        signature=user_in.signature,
    )
    session.add(user)
    await session.flush()
    return user


async def update_user(session: AsyncSession, user_id: int, **kwargs) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None
    for field, value in kwargs.items():
        if field != "id" and hasattr(user, field):
            setattr(user, field, value)
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user_id: int) -> User | None:
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
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
