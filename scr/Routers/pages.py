from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.database import db_helper
from scr.dbase import crud_users, crud_requests, crud_counterparties
from scr.dbase import crud_organizations, crud_manager, crud_directors, crud_positions
from scr.dbase.models import RequestStatus

templates = Jinja2Templates(directory="templates")
pages_router = APIRouter(tags=["Pages"])

SESSION_KEY = "user_email"


async def get_current_user(request: Request, session: AsyncSession):
    email = request.cookies.get(SESSION_KEY)
    if email:
        return await crud_users.get_user_by_email(session, email)
    return None


@pages_router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None})


@pages_router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await crud_users.authenticate_user(session, email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный email или пароль", "user": None},
        )
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return response


@pages_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": None})


@pages_router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from scr.dbase.schemas.schemas import UserCreate

    existing = await crud_users.get_user_by_email(session, email)
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email уже зарегистрирован", "user": None},
        )
    user = await crud_users.create_user(session, UserCreate(name=name, email=email, password=password))
    await session.commit()
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return response


@pages_router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(key=SESSION_KEY)
    return response


@pages_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    requests_list, _ = await crud_requests.get_requests(session, page=1, per_page=15)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "requests": requests_list, "statuses": RequestStatus, "active_page": "dashboard"},
    )


# --- Requests ---
@pages_router.get("/requests", response_class=HTMLResponse)
async def requests_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    requests_list, total = await crud_requests.get_requests(session, page=page)
    per_page = 20
    pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "requests/list.html",
        {"request": request, "user": user, "items": requests_list, "page": page, "pages": pages, "total": total, "statuses": RequestStatus, "active_page": "requests"},
    )


@pages_router.get("/requests/create", response_class=HTMLResponse)
async def request_create_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    cps, _ = await crud_counterparties.get_counterparties(session, per_page=100)
    return templates.TemplateResponse(
        "requests/create.html",
        {"request": request, "user": user, "counterparties": cps, "statuses": RequestStatus, "active_page": "requests"},
    )


@pages_router.post("/requests/create", response_class=HTMLResponse)
async def request_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    from scr.dbase.schemas.schemas import RequestCreateSchema
    from scr.dbase.models import RequestStatus as RS

    data = {
        "counterparty_id": int(form["counterparty_id"]),
        "description": form.get("description", ""),
        "notes": form.get("notes", ""),
        "status": form.get("status", RS.ZAPROS.value),
    }
    for f in ["bktpb", "ktpb", "ktp", "kso_393", "kso_204", "k_104", "k_104m", "sho", "pku", "pus", "parn"]:
        data[f] = int(form.get(f, 0))

    # Find manager by user email
    mgr, _ = await crud_manager.get_managers(session, search=user.email, per_page=1)
    manager_id = mgr[0].id if mgr else 1

    from scr.dbase.schemas.schemas import RequestCreateSchema
    schema = RequestCreateSchema(**data)
    await crud_requests.add_request(session, schema, manager_id=manager_id, created_by=user.name)
    await session.commit()
    return RedirectResponse("/requests", status_code=302)


@pages_router.get("/requests/{req_id}", response_class=HTMLResponse)
async def request_detail_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("Запрос не найден", status_code=404)
    return templates.TemplateResponse(
        "requests/detail.html",
        {"request": request, "user": user, "req": req, "active_page": "requests"},
    )


# --- Counterparties ---
@pages_router.get("/counterparties", response_class=HTMLResponse)
async def counterparties_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    items, total = await crud_counterparties.get_counterparties(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "counterparties/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "counterparties", "statuses": RequestStatus},
    )


@pages_router.get("/counterparties/{cp_id}", response_class=HTMLResponse)
async def counterparties_detail_page(
    cp_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    cp = await crud_counterparties.get_counterparty_by_id(session, cp_id)
    if not cp:
        return HTMLResponse("Контрагент не найден", status_code=404)
    reqs, _ = await crud_requests.get_requests(session, counterparty_id=cp_id, per_page=100)
    companies, _ = await crud_organizations.get_organizations(session, per_page=100)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    managers_list, _ = await crud_manager.get_managers(session, per_page=100)
    return templates.TemplateResponse(
        "counterparties/detail.html",
        {"request": request, "user": user, "cp": cp, "reqs": reqs, "statuses": RequestStatus,
         "companies": companies, "directors": directors, "managers": managers_list, "active_page": "counterparties"},
    )


@pages_router.delete("/counterparties/{cp_id}/delete")
async def counterparties_delete(
    cp_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, status_code=401)
    result = await crud_counterparties.delete_counterparty(session, cp_id)
    if not result:
        return JSONResponse({"error": "Контрагент не найден"}, status_code=404)
    await session.commit()
    return JSONResponse({"ok": True})


# --- Companies ---
@pages_router.get("/companies", response_class=HTMLResponse)
async def companies_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    items, total = await crud_organizations.get_organizations(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "companies/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "companies"},
    )


@pages_router.get("/companies/create", response_class=HTMLResponse)
async def companies_create_page(
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    managers_list, _ = await crud_manager.get_managers(session, per_page=100)
    return templates.TemplateResponse(
        "companies/create.html",
        {"request": request, "user": user, "directors": directors, "managers": managers_list, "back_to": back_to, "active_page": "companies"},
    )


@pages_router.get("/companies/{org_id}/edit", response_class=HTMLResponse)
async def companies_edit_page(
    org_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    org = await crud_organizations.get_organization_by_id(session, org_id)
    if not org:
        return HTMLResponse("Компания не найдена", status_code=404)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    managers_list, _ = await crud_manager.get_managers(session, per_page=100)
    return templates.TemplateResponse(
        "companies/edit.html",
        {"request": request, "user": user, "org": org, "directors": directors, "managers": managers_list, "back_to": back_to, "active_page": "companies"},
    )


# --- Managers ---
@pages_router.get("/managers", response_class=HTMLResponse)
async def managers_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    items, total = await crud_manager.get_managers(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "managers/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "managers"},
    )


# --- Directors ---
@pages_router.get("/directors", response_class=HTMLResponse)
async def directors_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    items, total = await crud_directors.get_dirs(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "directors/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "directors"},
    )


@pages_router.get("/directors/{dir_id}", response_class=HTMLResponse)
async def directors_detail_page(
    dir_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    dir = await crud_directors.get_dir_to_id(session, dir_id)
    if not dir:
        return HTMLResponse("Директор не найден", status_code=404)
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    return templates.TemplateResponse(
        "directors/detail.html",
        {"request": request, "user": user, "dir": dir, "positions": positions, "back_to": back_to, "active_page": "directors"},
    )


# --- Positions ---
@pages_router.get("/positions", response_class=HTMLResponse)
async def positions_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    items, total = await crud_positions.get_all_positions(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "positions/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "positions"},
    )
