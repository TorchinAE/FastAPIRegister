from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_users
from scr.dbase.schemas.schemas import UserCreate, UserLogin, UserResponse

auth_router = APIRouter(prefix="/api/auth", tags=["Auth"])

SESSION_KEY = "user_email"


@auth_router.post("/register", response_model=UserResponse)
async def register(
    user_in: UserCreate,
    response: Response,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    existing = await crud_users.get_user_by_email(session, user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    user = await crud_users.create_user(session, user_in)
    await session.commit()
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return user


@auth_router.post("/login", response_model=UserResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await crud_users.authenticate_user(
        session, credentials.email, credentials.password
    )
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return user


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=SESSION_KEY)
    return {"message": "Выход выполнен"}


@auth_router.get("/me", response_model=UserResponse)
async def get_me(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    email = request.cookies.get(SESSION_KEY)
    if not email:
        raise HTTPException(status_code=401, detail="Не авторизован")
    user = await crud_users.get_user_by_email(session, email)
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user
