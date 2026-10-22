import base64
import hashlib
import hmac
import time

import bcrypt
from sqlalchemy import Result, func, select
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


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ── Сброс пароля по ссылке из письма ──
# Токен без хранения в БД: id, срок и подпись HMAC (секрет приложения + текущий хэш пароля).
# После смены пароля хэш меняется — ссылка перестаёт действовать.


def _reset_signature(user: User, expires: int) -> str:
    from config import settings

    message = f"{user.id}:{expires}:{user.hashed_password}".encode()
    return hmac.new(settings.REG_SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def make_reset_token(user: User, ttl_hours: int) -> str:
    expires = int(time.time()) + ttl_hours * 3600
    raw = f"{user.id}:{expires}:{_reset_signature(user, expires)}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


async def get_user_by_reset_token(session: AsyncSession, token: str) -> User | None:
    """Пользователь по токену сброса; None — токен неверный, просрочен или пароль уже сменён."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        user_id, expires, signature = raw.split(":")
        user_id, expires = int(user_id), int(expires)
    except (ValueError, UnicodeDecodeError):
        return None
    if expires < time.time():
        return None
    user = await session.get(User, user_id)
    if not user or not hmac.compare_digest(signature, _reset_signature(user, expires)):
        return None
    return user


async def set_password(session: AsyncSession, user: User, password: str) -> None:
    user.hashed_password = hash_password(password)
    await session.flush()
