import os

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from scr.constants import LIST_ALL_ROWS, PASSWORD_MIN_LENGTH, REGISTRATION_DENIED_MSG, SECTION_PURPOSES
from scr.dbase import (
    crud_counterparties,
    crud_directors,
    crud_equipment,
    crud_invoices,
    crud_material_types,
    crud_materials,
    crud_module_types,
    crud_modules,
    crud_organizations,
    crud_payments,
    crud_positions,
    crud_requests,
    crud_settings,
    crud_users,
)
from scr.dbase.database import db_helper
from scr.dbase.models import Probability, RequestStatus

templates = Jinja2Templates(directory="templates")


def _money(value):
    try:
        parts = f"{float(value):,.2f}".replace(",", " ")
        return parts
    except (ValueError, TypeError):
        return "0.00"


templates.env.filters["money"] = _money
templates.env.globals["float"] = float
# Версия статики для сброса кеша браузера (nginx кеширует /static/ на 30 дней)
templates.env.globals["static_v"] = int(os.path.getmtime(os.path.join("static", "style.css")))

pages_router = APIRouter(tags=["Pages"])

SESSION_KEY = "user_email"


async def get_current_user(request: Request, session: AsyncSession):
    email = request.cookies.get(SESSION_KEY)
    if email:
        return await crud_users.get_user_by_email(session, email)
    return None


async def _get_per_page(session) -> int:
    val = await crud_settings.get_setting(session, "materials_per_page")
    return int(val) if val else 30


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
    response = RedirectResponse("/reg/requests", status_code=302)
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return response


@pages_router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    from config import settings

    return templates.TemplateResponse(
        "register.html", {"request": request, "user": None, "my_domen": settings.MY_DOMEN}
    )


@pages_router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from config import settings as app_settings
    from scr.dbase.schemas.schemas import UserCreate

    existing = await crud_users.get_user_by_email(session, email)
    if existing:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email уже зарегистрирован", "user": None, "my_domen": app_settings.MY_DOMEN},
        )
    if app_settings.MY_DOMEN:
        domain = email.split("@")[-1].lower()
        if domain != app_settings.MY_DOMEN.lower():
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "error": REGISTRATION_DENIED_MSG,
                    "user": None,
                    "my_domen": app_settings.MY_DOMEN,
                },
            )
    user = await crud_users.create_user(session, UserCreate(name=name, email=email, password=password))
    await session.commit()
    response = RedirectResponse("/reg/requests", status_code=302)
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    from scr.utils.email import send_registration_notification

    await send_registration_notification(user.email, user.name)
    return response


@pages_router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    token: str = "",
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Ввод нового пароля по ссылке из письма."""
    target = await crud_users.get_user_by_reset_token(session, token)
    context = {"request": request, "user": None, "token": token, "min_length": PASSWORD_MIN_LENGTH}
    if not target:
        context["invalid"] = True
    else:
        context["email"] = target.email
    return templates.TemplateResponse("reset_password.html", context)


@pages_router.post("/reset-password", response_class=HTMLResponse)
async def reset_password_submit(
    request: Request,
    token: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    target = await crud_users.get_user_by_reset_token(session, token)
    context = {"request": request, "user": None, "token": token, "min_length": PASSWORD_MIN_LENGTH}
    if not target:
        context["invalid"] = True
        return templates.TemplateResponse("reset_password.html", context)
    context["email"] = target.email
    if len(password) < PASSWORD_MIN_LENGTH:
        context["error"] = f"Пароль — не короче {PASSWORD_MIN_LENGTH} символов"
    elif password != password2:
        context["error"] = "Пароли не совпадают"
    if "error" in context:
        return templates.TemplateResponse("reset_password.html", context)
    await crud_users.set_password(session, target, password)
    await session.commit()
    context["done"] = True
    return templates.TemplateResponse("reset_password.html", context)


@pages_router.get("/logout")
async def logout():
    response = RedirectResponse("/reg/", status_code=302)
    response.delete_cookie(key=SESSION_KEY)
    return response


# --- Requests ---
@pages_router.get("/requests", response_class=HTMLResponse)
async def requests_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    requests_list, total = await crud_requests.get_requests(session, page=1, per_page=LIST_ALL_ROWS)

    # Load contract specs for the current page's requests
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import selectinload

    from scr.dbase.models import ContractSpec

    req_ids = [r.id for r in requests_list]
    specs_map = {}
    if req_ids:
        specs_result = await session.execute(
            sa_select(ContractSpec)
            .where(ContractSpec.request_id.in_(req_ids))
            .options(selectinload(ContractSpec.company))
        )
        for spec in specs_result.scalars().all():
            specs_map[spec.request_id] = spec

    return templates.TemplateResponse(
        "requests/list.html",
        {
            "request": request,
            "user": user,
            "items": requests_list,
            "per_page": per_page,
            "total": total,
            "statuses": RequestStatus,
            "active_page": "requests",
            "specs_map": specs_map,
        },
    )


@pages_router.get("/requests/create", response_class=HTMLResponse)
async def request_create_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase.schemas.schemas import RequestCreateSchema

    # Create minimal request with auto-filled fields
    schema = RequestCreateSchema()
    new_req = await crud_requests.add_request(
        session, schema, manager_id=user.id, created_by=user.name, user_city=user.city
    )
    await session.commit()
    # new=1 — только что созданная пустая заявка: удаляется при уходе со страницы без изменений
    return RedirectResponse(f"/reg/requests/{new_req.id}?new=1", status_code=302)


@pages_router.post("/requests/create", response_class=HTMLResponse)
async def request_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    from scr.dbase.models import RequestStatus as RS
    from scr.dbase.schemas.schemas import RequestCreateSchema

    data = {
        "counterparty_id": int(form["counterparty_id"]),
        "description": form.get("description", ""),
        "notes": form.get("notes", ""),
        "status": form.get("status", RS.ZAPROS.value),
        "cost": float(form.get("cost", 0)),
        "issue_date": form.get("issue_date") or None,
        "incoming_letter_num": form.get("incoming_letter_num") or None,
        "repeat_tkp": form.get("repeat_tkp") or None,
        "invoice_num": form.get("invoice_num") or None,
        "invoice_date": form.get("invoice_date") or None,
        "factory_order_num": form.get("factory_order_num") or None,
        "factory_order_date": form.get("factory_order_date") or None,
        "ship_date": form.get("ship_date") or None,
        "bktpb": int(form.get("bktpb", 0)),
        "ktpb": int(form.get("ktpb", 0)),
        "ktp": int(form.get("ktp", 0)),
        "kso_393": int(form.get("kso_393", 0)),
        "kso_204": int(form.get("kso_204", 0)),
        "k_104": int(form.get("k_104", 0)),
        "k_104m": int(form.get("k_104m", 0)),
        "sho": int(form.get("sho", 0)),
        "pku": int(form.get("pku", 0)),
        "pus": int(form.get("pus", 0)),
        "parn": int(form.get("parn", 0)),
    }
    if form.get("equipment_id"):
        data["equipment_id"] = int(form["equipment_id"])

    # Find user by email to set as manager
    users_list, _ = await crud_users.get_users(session, search=user.email, per_page=1)
    manager_id = users_list[0].id if users_list else 1

    schema = RequestCreateSchema(**data)
    await crud_requests.add_request(session, schema, manager_id=manager_id, created_by=user.name, user_city=user.city)
    await session.commit()
    return RedirectResponse("/reg/requests", status_code=302)


@pages_router.get("/requests/{req_id}", response_class=HTMLResponse)
async def request_detail_page(
    req_id: int,
    request: Request,
    new: bool = False,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    cps, _ = await crud_counterparties.get_counterparties(session, per_page=100)
    users_list, _ = await crud_users.get_users(session, per_page=100)
    equipment_list, _ = await crud_equipment.get_equipment_list(session, per_page=100)
    companies_list, _ = await crud_organizations.get_organizations(session, per_page=100)
    from sqlalchemy import select as sa_select

    related, _ = (
        await crud_requests.get_requests(session, company_id=req.company_id, per_page=50) if req.company_id else ([], 0)
    )
    invoices = await crud_invoices.get_invoices_by_request(session, req_id)
    payment_items = await crud_payments.ensure_payment_items(session, req_id)
    # Строки порядка оплаты создаются при первом открытии — без commit они откатываются,
    # и сохранение по их id возвращает 404
    await session.commit()
    all_settings = await crud_settings.get_all_settings(session)
    settings_dict = {s.key: s.value for s in all_settings}
    probs_result = await session.execute(sa_select(Probability).order_by(Probability.id))
    probabilities = list(probs_result.scalars().all())
    return templates.TemplateResponse(
        "requests/detail.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "is_new": new and not req.counterparty_id,
            "counterparties": cps,
            "users_list": users_list,
            "equipment": equipment_list,
            "companies": companies_list,
            "related_requests": related,
            "statuses": RequestStatus,
            "invoices": invoices,
            "payment_items": payment_items,
            "settings": settings_dict,
            "probabilities": probabilities,
            "active_page": "requests",
        },
    )


@pages_router.post("/requests/{req_id}", response_class=HTMLResponse)
async def request_edit_submit(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    from scr.dbase.schemas.schemas import RequestUpdateSchema

    data = {"id": req_id}
    if form.get("contact_id"):
        data["counterparty_id"] = int(form["contact_id"])
    if form.get("company_id"):
        data["company_id"] = int(form["company_id"])
    if form.get("manager_id"):
        data["manager_id"] = int(form["manager_id"])
    if form.get("equipment_id"):
        data["equipment_id"] = int(form["equipment_id"])
    if form.get("probability_id"):
        data["probability_id"] = int(form["probability_id"])
    if form.get("project_stamp") is not None:
        data["project_stamp"] = form["project_stamp"]
    if form.get("description") is not None:
        data["description"] = form["description"]
    if form.get("notes") is not None:
        data["notes"] = form["notes"]
    if form.get("status"):
        data["status"] = form["status"]
    if form.get("cost") is not None:
        data["cost"] = float(form["cost"])
    if form.get("issue_date"):
        data["issue_date"] = form["issue_date"]
    for text_field in ("incoming_letter_num", "repeat_tkp", "factory_order_num"):
        if form.get(text_field):
            data[text_field] = form[text_field]
    for date_field in ("factory_order_date", "ship_date"):
        if form.get(date_field):
            data[date_field] = form[date_field]
    for eq_field in ("bktpb", "ktpb", "ktp", "kso_393", "kso_204", "k_104", "k_104m", "sho", "pku", "pus", "parn"):
        if form.get(eq_field) is not None:
            data[eq_field] = int(form[eq_field])

    schema = RequestUpdateSchema(**data)
    await crud_requests.update_request(session, schema)
    await session.commit()
    return RedirectResponse(f"/requests/{req_id}", status_code=302)


# --- Counterparties ---
@pages_router.get("/counterparties", response_class=HTMLResponse)
async def counterparties_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_counterparties.get_counterparties(session, page=1, per_page=LIST_ALL_ROWS)
    companies, _ = await crud_organizations.get_organizations(session, per_page=100)
    return templates.TemplateResponse(
        "counterparties/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "companies": companies,
            "per_page": per_page,
            "total": total,
            "active_page": "counterparties",
            "statuses": RequestStatus,
        },
    )


@pages_router.post("/counterparties", response_class=HTMLResponse)
async def counterparties_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip()
    if name and email:
        from scr.dbase.schemas.schemas import CounterpartyCreateSchema

        data = {
            "name": name,
            "email": email,
            "phone": form.get("phone") or None,
            "company_id": int(form["company_id"]),
        }
        await crud_counterparties.add_counterparty(session, CounterpartyCreateSchema(**data), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/counterparties", status_code=302)


@pages_router.get("/counterparties/{cp_id}", response_class=HTMLResponse)
async def counterparties_detail_page(
    cp_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    cp = await crud_counterparties.get_counterparty_by_id(session, cp_id)
    if not cp:
        return HTMLResponse("Контрагент не найден", status_code=404)
    reqs, _ = await crud_requests.get_requests(session, counterparty_id=cp_id, per_page=100)
    companies, _ = await crud_organizations.get_organizations(session, per_page=100)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    return templates.TemplateResponse(
        "counterparties/detail.html",
        {
            "request": request,
            "user": user,
            "cp": cp,
            "reqs": reqs,
            "statuses": RequestStatus,
            "companies": companies,
            "directors": directors,
            "active_page": "counterparties",
        },
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
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_organizations.get_organizations(session, page=1, per_page=LIST_ALL_ROWS)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    return templates.TemplateResponse(
        "companies/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "directors": directors,
            "per_page": per_page,
            "total": total,
            "active_page": "companies",
        },
    )


@pages_router.post("/companies", response_class=HTMLResponse)
async def companies_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import OrganizationAddSchema

        data = {
            "name": name,
            "inn": form.get("inn") or None,
            "address": form.get("address") or None,
            "profitability": float(form.get("profitability") or 15),
            "director_id": int(form["director_id"]),
        }
        await crud_organizations.add_organization(session, OrganizationAddSchema(**data), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/companies", status_code=302)


@pages_router.get("/companies/create", response_class=HTMLResponse)
async def companies_create_page(
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    return templates.TemplateResponse(
        "companies/create.html",
        {"request": request, "user": user, "directors": directors, "back_to": back_to, "active_page": "companies"},
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
        return RedirectResponse("/reg/", status_code=302)
    org = await crud_organizations.get_organization_by_id(session, org_id)
    if not org:
        return HTMLResponse("Компания не найдена", status_code=404)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    reqs, _ = await crud_requests.get_requests(session, company_id=org_id, per_page=100)
    return templates.TemplateResponse(
        "companies/edit.html",
        {
            "request": request,
            "user": user,
            "org": org,
            "directors": directors,
            "reqs": reqs,
            "back_to": back_to,
            "active_page": "companies",
        },
    )


# --- Users (Пользователи) ---
@pages_router.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_users.get_users(session, page=1, per_page=LIST_ALL_ROWS)
    return templates.TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "per_page": per_page,
            "total": total,
            "active_page": "users",
        },
    )


@pages_router.post("/users", response_class=HTMLResponse)
async def users_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip()
    if name and email:
        existing = await crud_users.get_user_by_email(session, email)
        if not existing:
            from scr.dbase.schemas.schemas import UserCreate

            await crud_users.create_user(
                session,
                UserCreate(
                    name=name,
                    email=email,
                    password="123456",
                    city=form.get("city", "ив").strip() or "ив",
                    signature=form.get("signature") or None,
                ),
            )
            await session.commit()
    return RedirectResponse("/reg/users", status_code=302)


@pages_router.get("/users/{user_id}", response_class=HTMLResponse)
async def users_detail_page(
    user_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    target = await crud_users.get_user_by_id(session, user_id)
    if not target:
        return HTMLResponse("Пользователь не найден", status_code=404)
    all_users, _ = await crud_users.get_users(session, per_page=100)
    other_users = [u for u in all_users if u.id != user_id]
    return templates.TemplateResponse(
        "users/detail.html",
        {
            "request": request,
            "user": user,
            "target": target,
            "other_users": other_users,
            "back_to": back_to,
            "active_page": "users",
        },
    )


# --- Directors ---
@pages_router.get("/directors", response_class=HTMLResponse)
async def directors_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_directors.get_dirs(session, page=1, per_page=LIST_ALL_ROWS)
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    return templates.TemplateResponse(
        "directors/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "positions": positions,
            "per_page": per_page,
            "total": total,
            "active_page": "directors",
        },
    )


@pages_router.post("/directors", response_class=HTMLResponse)
async def directors_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import DirectorSchema

        data = {
            "name": name,
            "email": form.get("email") or None,
            "phone": form.get("phone") or None,
            "position_id": int(form["position_id"]),
        }
        await crud_directors.add_dir(session, DirectorSchema(**data), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/directors", status_code=302)


@pages_router.get("/directors/create", response_class=HTMLResponse)
async def directors_create_page(
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    return templates.TemplateResponse(
        "directors/create.html",
        {"request": request, "user": user, "positions": positions, "back_to": back_to, "active_page": "directors"},
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
        return RedirectResponse("/reg/", status_code=302)
    dir = await crud_directors.get_dir_to_id(session, dir_id)
    if not dir:
        return HTMLResponse("Директор не найден", status_code=404)
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    return templates.TemplateResponse(
        "directors/detail.html",
        {
            "request": request,
            "user": user,
            "dir": dir,
            "positions": positions,
            "back_to": back_to,
            "active_page": "directors",
        },
    )


@pages_router.delete("/directors/{dir_id}/delete")
async def directors_delete(
    dir_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, status_code=401)
    result = await crud_directors.delete_dir(session, dir_id)
    if not result:
        return JSONResponse({"error": "Директор не найден"}, status_code=404)
    await session.commit()
    return JSONResponse({"ok": True})


# --- Positions ---
@pages_router.get("/positions", response_class=HTMLResponse)
async def positions_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_positions.get_all_positions(session, page=1, per_page=LIST_ALL_ROWS)
    return templates.TemplateResponse(
        "positions/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "per_page": per_page,
            "total": total,
            "active_page": "positions",
        },
    )


@pages_router.post("/positions", response_class=HTMLResponse)
async def positions_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import PositionCreateSchema

        await crud_positions.add_position(session, PositionCreateSchema(name=name), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/positions", status_code=302)


@pages_router.get("/positions/{pos_id}", response_class=HTMLResponse)
async def positions_detail_page(
    pos_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    pos = await crud_positions.get_position_id(session, pos_id)
    if not pos:
        return HTMLResponse("Должность не найдена", status_code=404)
    return templates.TemplateResponse(
        "positions/detail.html",
        {"request": request, "user": user, "pos": pos, "back_to": back_to, "active_page": "positions"},
    )


# --- Equipment ---
@pages_router.get("/equipment", response_class=HTMLResponse)
async def equipment_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_equipment.get_equipment_list(session, page=1, per_page=LIST_ALL_ROWS)
    return templates.TemplateResponse(
        "equipment/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "per_page": per_page,
            "total": total,
            "active_page": "equipment",
        },
    )


@pages_router.post("/equipment", response_class=HTMLResponse)
async def equipment_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import EquipmentCreateSchema

        await crud_equipment.add_equipment(session, EquipmentCreateSchema(name=name), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/equipment", status_code=302)


@pages_router.get("/equipment/{eq_id}", response_class=HTMLResponse)
async def equipment_detail_page(
    eq_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    eq = await crud_equipment.get_equipment_by_id(session, eq_id)
    if not eq:
        return HTMLResponse("Оборудование не найдено", status_code=404)
    reqs, _ = await crud_requests.get_requests(session, per_page=1000)
    eq_reqs = [r for r in reqs if r.equipment_id == eq_id]
    return templates.TemplateResponse(
        "equipment/detail.html",
        {
            "request": request,
            "user": user,
            "eq": eq,
            "eq_reqs": eq_reqs,
            "back_to": back_to,
            "active_page": "equipment",
            "statuses": RequestStatus,
        },
    )


@pages_router.delete("/equipment/{eq_id}/delete")
async def equipment_delete(
    eq_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, status_code=401)
    result = await crud_equipment.delete_equipment(session, eq_id)
    if not result:
        return JSONResponse({"error": "Оборудование не найдено"}, status_code=404)
    await session.commit()
    return JSONResponse({"ok": True})


# --- Settings ---
@pages_router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    all_settings = await crud_settings.get_all_settings(session)
    return templates.TemplateResponse(
        "settings/list.html",
        {"request": request, "user": user, "settings": all_settings, "active_page": "settings"},
    )


@pages_router.get("/invoices", response_class=HTMLResponse)
async def invoices_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from scr.dbase.models import Invoice
    from scr.dbase.models import Request as ReqModel

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.request).selectinload(ReqModel.manager))
        .options(selectinload(Invoice.request).selectinload(ReqModel.company))
        .options(selectinload(Invoice.request).selectinload(ReqModel.equipment))
        .order_by(Invoice.id.desc())
    )
    count_stmt = select(func.count(Invoice.id))
    total = (await session.execute(count_stmt)).scalar() or 0
    per_page = await _get_per_page(session)
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    return templates.TemplateResponse(
        "invoices/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "per_page": per_page,
            "total": total,
            "active_page": "invoices",
        },
    )


# Разделы, у которых на странице расчёта показывается сумма блоков
BLOCK_TOTAL_SECTIONS = ("corpusa", "kso", "kru", "sho")


@pages_router.get("/requests/{req_id}/calc", response_class=HTMLResponse)
async def request_calc_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)

    # Folder creation on calc page visit
    folder_path = None
    import os
    import shutil

    adres_server = await crud_settings.get_setting(session, "adres_server") or ""
    tkp_template_folder = await crud_settings.get_setting(session, "tkp_template_folder") or ""

    from scr.dbase.crud_kso204 import tkp_folder_path

    folder_path = tkp_folder_path(adres_server, req)
    if folder_path:
        try:
            os.makedirs(folder_path, exist_ok=True)
            os.makedirs(
                os.path.join(
                    folder_path, "\u041e\u043f\u0440\u043e\u0441\u043d\u044b\u0435 \u043b\u0438\u0441\u0442\u044b"
                ),
                exist_ok=True,
            )
            if tkp_template_folder and os.path.isdir(tkp_template_folder):
                for item in os.listdir(tkp_template_folder):
                    src = os.path.join(tkp_template_folder, item)
                    dst = os.path.join(folder_path, item)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
        except OSError:
            pass

    # Поле «ТКП» — итого без НДС по сводной таблице
    from scr.dbase.crud_module_slots import sync_hidden_slots
    from scr.dbase.crud_tkp import build_tkp_summary

    if await sync_hidden_slots(session, req.id):
        await session.commit()
    summary = await build_tkp_summary(session, req)
    tkp_total = round(summary["totals"]["final"], 2)
    if float(req.tkp_calc_cost or 0) != tkp_total:
        req.tkp_calc_cost = tkp_total
        await session.commit()

    # Корпуса, КСО, КРУ, ЩО — сумма по блокам расчёта (стоимость × кол-во) и количество блоков
    block_totals = {
        r["slug"]: {"final": r["final"], "qty": r["quantity"]}
        for r in summary["rows"]
        if r["slug"] in BLOCK_TOTAL_SECTIONS
    }
    if "corpusa" in block_totals:
        from sqlalchemy import func as sa_func
        from sqlalchemy import select as sa_select

        from scr.dbase.models import ModuleType, RequestCalc

        qty_stmt = (
            sa_select(sa_func.coalesce(sa_func.sum(RequestCalc.quantity), 0))
            .join(ModuleType, ModuleType.id == RequestCalc.module_type_id)
            .where(RequestCalc.request_id == req.id, ModuleType.slug == "corpusa")
        )
        block_totals["corpusa"]["qty"] = (await session.execute(qty_stmt)).scalar() or 0

    return templates.TemplateResponse(
        "requests/calc.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "folder_path": folder_path or "",
            "totals": summary["totals"],
            "nds_percent": summary["nds_percent"],
            "block_totals": block_totals,
            "active_page": "requests",
        },
    )


@pages_router.get("/requests/{req_id}/calc/tkp", response_class=HTMLResponse)
async def request_calc_tkp_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    try:
        return await _render_tkp_page(request, user, req, session)
    except Exception as e:  # noqa: BLE001
        return HTMLResponse(f"Ошибка: {e}", status_code=500)


async def _render_tkp_page(request, user, req, session):
    from scr.dbase.crud_module_slots import sync_hidden_slots
    from scr.dbase.crud_tkp import build_tkp_kit, build_tkp_summary

    if await sync_hidden_slots(session, req.id):
        await session.commit()
    summary = await build_tkp_summary(session, req)
    kit = await build_tkp_kit(session, req)
    kit_total = sum(b["sum"] for s in kit for b in s["blocks"])
    return templates.TemplateResponse(
        "requests/calc_tkp.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "kit": kit,
            "kit_total": kit_total,
            "rows": summary["rows"],
            "totals": summary["totals"],
            "nds_percent": summary["nds_percent"],
            "active_page": "requests",
        },
    )


@pages_router.get("/requests/{req_id}/calc/delivery", response_class=HTMLResponse)
async def request_calc_delivery_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse(
            "\u0422\u041a\u041f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", status_code=404
        )

    from scr.dbase import crud_deliveries

    delivery = await crud_deliveries.get_or_create_delivery(session, req_id)
    await session.commit()

    # Use saved profitability from delivery, fall back to company default
    if delivery.profitability_percent and float(delivery.profitability_percent) > 0:
        profitability = float(delivery.profitability_percent)
    elif req.company:
        profitability = float(req.company.profitability) if req.company.profitability else 0.0
    else:
        profitability = 0.0

    return templates.TemplateResponse(
        "requests/calc_delivery.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "delivery": delivery,
            "profitability": profitability,
            "active_page": "requests",
        },
    )


@pages_router.get("/requests/{req_id}/calc/{section}", response_class=HTMLResponse)
async def request_calc_page_by_section(
    req_id: int,
    section: str,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    if section == "tkp":
        return RedirectResponse(f"/reg/requests/{req_id}/calc/tkp", status_code=302)
    if section == "delivery":
        return RedirectResponse(f"/reg/requests/{req_id}/calc/delivery", status_code=302)
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    mt = await crud_module_types.get_module_type_by_slug(session, section)
    if not mt:
        return HTMLResponse("Раздел не найден", status_code=404)
    from scr.dbase import crud_module_slots, crud_module_templates

    await crud_module_slots.sync_hidden_slots(session, req_id)
    calcs = await crud_module_types.get_or_create_calcs(session, req_id, mt.id)
    works = section in crud_module_types.WORKS_SECTIONS
    tpls = [] if works else await crud_module_templates.get_templates(session, mt.id)
    await session.commit()
    _, prices, modules_data = await _sorted_modules(session)
    default_profit = await crud_module_types.default_profitability(session, req_id)
    slots = await crud_module_slots.get_slots(session, mt.id)
    blocks = [crud_module_types.calc_block_data(c, prices, default_profit, slots) for c in calcs]
    return templates.TemplateResponse(
        "requests/calc_module.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "mt": mt,
            "blocks": blocks,
            "modules_data": modules_data,
            "slots": [crud_module_slots.slot_json(sl) for sl in slots if not sl.hidden],
            "prices": prices,
            "multi": section in crud_module_types.MULTI_BLOCK_SECTIONS,
            "split_qty": section in crud_module_types.SPLIT_QTY_SECTIONS,
            "purposes": SECTION_PURPOSES.get(section, []),
            "works": works,
            "templates_list": [{"id": t.id, "name": t.name, "purpose": t.purpose or ""} for t in tpls],
            "active_page": "requests",
        },
    )


def _modules_data(modules_list, prices: dict[int, float], attrs: dict[int, dict]) -> list[dict]:
    """Модули для выпадающих списков расчёта: тип (подбор в строку и цвет подсветки) и характеристики для фильтров."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "type_id": m.material_type_id,
            "type_name": m.material_type.name if m.material_type else "",
            "color": m.material_type.color if m.material_type else None,
            "price": prices.get(m.id, 0.0),
            "nom_tok": m.nom_tok or 0,
            **attrs.get(m.id, {}),
        }
        for m in modules_list
    ]


async def _sorted_modules(session) -> tuple[list, dict[int, float], list[dict]]:
    """Все модули в порядке «ном. ток, класс точности, название», цены и данные для страниц расчёта."""
    modules_list, _ = await crud_modules.get_modules(session, per_page=LIST_ALL_ROWS)
    attrs = await crud_modules.get_module_attrs(session)
    modules_list = await crud_modules.sort_modules(session, modules_list, attrs)
    prices = await crud_modules.get_module_prices(session)
    return modules_list, prices, _modules_data(modules_list, prices, attrs)


# --- Nominal Currents ---
@pages_router.get("/nominal-currents", response_class=HTMLResponse)
async def nominal_currents_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from sqlalchemy import func, select

    from scr.dbase import crud_nominal_currents
    from scr.dbase.models import Material, Module

    items = await crud_nominal_currents.get_all(session)
    usage: dict[int, int] = {}
    for model in (Material, Module):
        stmt = select(model.nom_tok, func.count(model.id)).where(model.nom_tok > 0).group_by(model.nom_tok)
        for value, count in (await session.execute(stmt)).all():
            usage[value] = usage.get(value, 0) + count
    return templates.TemplateResponse(
        "nominal_currents/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "usage": usage,
            "total": len(items),
            "active_page": "nominal_currents",
        },
    )


# --- Units ---
@pages_router.get("/units", response_class=HTMLResponse)
async def units_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from sqlalchemy import func, select

    from scr.constants import DEFAULT_UNIT
    from scr.dbase import crud_units
    from scr.dbase.models import Material

    items = await crud_units.get_all(session)
    stmt = select(Material.unit, func.count(Material.id)).group_by(Material.unit)
    usage = dict((await session.execute(stmt)).all())
    return templates.TemplateResponse(
        "units/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "usage": usage,
            "default_unit": DEFAULT_UNIT,
            "total": len(items),
            "active_page": "units",
        },
    )


# --- Accuracy Classes ---
@pages_router.get("/accuracy-classes", response_class=HTMLResponse)
async def accuracy_classes_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from sqlalchemy import func, select

    from scr.dbase import crud_accuracy_classes
    from scr.dbase.models import Material

    items = await crud_accuracy_classes.get_all(session)
    stmt = (
        select(Material.accuracy_class, func.count(Material.id))
        .where(Material.accuracy_class.is_not(None))
        .group_by(Material.accuracy_class)
    )
    usage = dict((await session.execute(stmt)).all())
    return templates.TemplateResponse(
        "accuracy_classes/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "usage": usage,
            "total": len(items),
            "active_page": "accuracy_classes",
        },
    )


# --- Module Types Calc ---
@pages_router.get("/module-types-calc", response_class=HTMLResponse)
async def module_types_calc_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items = await crud_module_types.get_module_types(session)
    return templates.TemplateResponse(
        "module_types_calc/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "total": len(items),
            "active_page": "module_types_calc",
        },
    )


@pages_router.get("/module-type-slots", response_class=HTMLResponse)
async def module_type_slots_page(
    request: Request,
    type: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    """Обязательные строки разделов расчёта с модулями (без доставки и работ)."""
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase import crud_material_types, crud_module_slots

    excluded = crud_module_types.WORKS_SECTIONS | {"delivery"}
    types = [t for t in await crud_module_types.get_module_types(session) if t.slug not in excluded]
    mt = next((t for t in types if t.slug == type), types[0] if types else None)
    slots = await crud_module_slots.get_slots(session, mt.id) if mt else []
    material_types, _ = await crud_material_types.get_all_types(session, per_page=10000)
    return templates.TemplateResponse(
        "module_types_calc/slots.html",
        {
            "request": request,
            "user": user,
            "types": types,
            "mt": mt,
            "slots": [crud_module_slots.slot_json(sl) for sl in slots],
            "material_types": [{"id": t.id, "name": t.name} for t in material_types],
            "active_page": "module_type_slots",
        },
    )


@pages_router.post("/module-types-calc", response_class=HTMLResponse)
async def module_types_calc_create(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    slug = _slugify(form.get("slug", "").strip() or name)
    if name and slug:
        from scr.dbase.schemas.schemas import ModuleTypeCreateSchema

        await crud_module_types.add_module_type(
            session, ModuleTypeCreateSchema(name=name, slug=slug), created_by=user.name
        )
        await session.commit()
    return RedirectResponse("/reg/module-types-calc", status_code=302)


_TRANSLIT = {
    **dict(
        zip(
            "абвгдеёжзийклмнопрстуфхцчшщыэюя",
            [
                "a",
                "b",
                "v",
                "g",
                "d",
                "e",
                "e",
                "zh",
                "z",
                "i",
                "y",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "r",
                "s",
                "t",
                "u",
                "f",
                "h",
                "ts",
                "ch",
                "sh",
                "sch",
                "y",
                "e",
                "yu",
                "ya",
            ],
            strict=True,
        )
    ),
    "ъ": "",
    "ь": "",
}


def _slugify(value: str) -> str:
    """Slug для URL: транслитерация, латиница/цифры/дефис."""
    import re

    text = "".join(_TRANSLIT.get(ch, ch) for ch in value.lower())
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


@pages_router.get("/module-types-calc/{type_id}/defaults", response_class=HTMLResponse)
async def module_types_defaults_page(
    type_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        return HTMLResponse("Тип модуля не найден", status_code=404)
    from scr.dbase import crud_finance, crud_module_slots, crud_module_templates

    tpls = await crud_module_templates.get_templates(session, type_id)
    await session.commit()
    slots = await crud_module_slots.get_slots(session, type_id)
    _, prices, modules_data = await _sorted_modules(session)

    payroll_items = await crud_finance.get_all_payroll_items(session)
    invoice_items = await crud_finance.get_all_invoice_items(session)
    return templates.TemplateResponse(
        "module_types_calc/defaults.html",
        {
            "request": request,
            "user": user,
            "mt": mt,
            "slots": [crud_module_slots.slot_json(sl) for sl in slots],
            "tpls": [crud_module_templates.template_json(t, slots, prices) for t in tpls],
            "modules_data": modules_data,
            "purposes": SECTION_PURPOSES.get(mt.slug, []),
            "payroll_items": payroll_items,
            "invoice_items": invoice_items,
            "active_page": "module_types_calc",
        },
    )


@pages_router.post("/module-types-calc/{type_id}/defaults", response_class=HTMLResponse)
async def module_types_defaults_save(
    type_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    mt = await crud_module_types.get_module_type_by_id(session, type_id)
    if not mt:
        return HTMLResponse("Тип модуля не найден", status_code=404)
    fot_val = form.get("fot_item_id", "")
    mt.fot_item_id = int(fot_val) if fot_val else None
    overhead_val = form.get("overhead_item_id", "")
    mt.overhead_item_id = int(overhead_val) if overhead_val else None
    await session.flush()
    await session.commit()
    return RedirectResponse(f"/reg/module-types-calc/{type_id}/defaults", status_code=302)


# --- Materials ---
@pages_router.get("/materials", response_class=HTMLResponse)
async def materials_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items = await crud_materials.get_all_materials(session)
    types, _ = await crud_material_types.get_all_types(session, per_page=10000)
    per_page = await _get_per_page(session)

    # Build set of material names that have modules
    from scr.dbase import crud_modules

    all_modules = await crud_modules.get_all_modules(session)
    module_names = {m.name for m in all_modules}
    from scr.dbase import crud_nominal_currents

    nom_tok_values = await crud_nominal_currents.get_values(session)

    await session.commit()
    from scr.dbase import crud_units

    units = await crud_units.get_names(session)
    from scr.dbase import crud_accuracy_classes

    accuracy_classes = await crud_accuracy_classes.get_names(session)
    return templates.TemplateResponse(
        "materials/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "types": types,
            "total": len(items),
            "per_page": per_page,
            "module_names": module_names,
            "nom_tok_values": nom_tok_values,
            "units": units,
            "accuracy_classes": accuracy_classes,
            "active_page": "materials",
        },
    )


@pages_router.post("/materials", response_class=HTMLResponse)
async def materials_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from datetime import date as date_cls

        from scr.dbase.schemas.schemas import MaterialCreateSchema

        data = {
            "name": name,
            "price": float(form.get("price", 0)),
            "code_1c": form.get("code_1c") or None,
            "code_agent": form.get("code_agent") or None,
            "url_agent": form.get("url_agent") or None,
            "nom_tok": int(form.get("nom_tok", 0)),
            "voltage": form.get("voltage") or None,
            "unit": (form.get("unit") or "").strip() or "шт",
            "accuracy_class": (form.get("accuracy_class") or "").strip() or None,
            "stats": form.get("stats") == "on",
            "vtych": form.get("vtych") == "on",
            "vykat": form.get("vykat") == "on",
            "ruchn": form.get("ruchn") == "on",
            "el_priv": form.get("el_priv") == "on",
        }
        date_str = form.get("date")
        if date_str:
            try:
                data["date"] = date_cls.fromisoformat(date_str)
            except (ValueError, TypeError):
                data["date"] = date_cls.today()
        else:
            data["date"] = date_cls.today()
        if form.get("type_id"):
            data["type_id"] = int(form["type_id"])
        await crud_materials.add_material(session, MaterialCreateSchema(**data), created_by=user.name)
        from scr.dbase import crud_nominal_currents

        await crud_nominal_currents.ensure_value(session, data["nom_tok"])
        from scr.dbase import crud_units

        await crud_units.ensure_name(session, data["unit"])
        from scr.dbase import crud_accuracy_classes

        await crud_accuracy_classes.ensure_name(session, data["accuracy_class"])
        await session.commit()
    return RedirectResponse("/reg/materials", status_code=302)


@pages_router.get("/materials/{mat_id}", response_class=HTMLResponse)
async def materials_detail_page(
    mat_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    mat = await crud_materials.get_material_by_id(session, mat_id)
    if not mat:
        return HTMLResponse("Материал не найден", status_code=404)
    types, _ = await crud_material_types.get_all_types(session, per_page=10000)
    from scr.dbase import crud_nominal_currents

    nom_tok_values = await crud_nominal_currents.get_values(session)
    from scr.dbase import crud_units

    units = await crud_units.get_names(session)
    from scr.dbase import crud_accuracy_classes

    accuracy_classes = await crud_accuracy_classes.get_names(session)
    return templates.TemplateResponse(
        "materials/detail.html",
        {
            "request": request,
            "user": user,
            "mat": mat,
            "types": types,
            "nom_tok_values": nom_tok_values,
            "units": units,
            "accuracy_classes": accuracy_classes,
            "back_to": back_to,
            "active_page": "materials",
        },
    )


# --- Material Types ---
@pages_router.get("/material-types", response_class=HTMLResponse)
async def material_types_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, total = await crud_material_types.get_all_types(session, page=1, per_page=LIST_ALL_ROWS)
    return templates.TemplateResponse(
        "material_types/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "per_page": per_page,
            "total": total,
            "active_page": "material_types",
        },
    )


@pages_router.post("/material-types", response_class=HTMLResponse)
async def material_types_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    back_to = form.get("back_to", "").strip()
    new_type_id = None
    if name:
        from scr.dbase.schemas.schemas import MaterialTypeCreateSchema

        new_type = await crud_material_types.add_type(
            session, MaterialTypeCreateSchema(name=name), created_by=user.name
        )
        await session.commit()
        new_type_id = new_type.id if new_type else None
    redirect_url = back_to or "/reg/material-types"
    if new_type_id and back_to:
        separator = "&" if "?" in back_to else "?"
        redirect_url = f"{back_to}{separator}new_type_id={new_type_id}"
    return RedirectResponse(redirect_url, status_code=302)


@pages_router.get("/material-types/create", response_class=HTMLResponse)
async def material_types_create_page(
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    return templates.TemplateResponse(
        "material_types/create.html",
        {"request": request, "user": user, "back_to": back_to, "active_page": "material_types"},
    )


@pages_router.get("/material-types/{type_id}", response_class=HTMLResponse)
async def material_types_detail_page(
    type_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    mt = await crud_material_types.get_type_by_id(session, type_id)
    if not mt:
        return HTMLResponse("Тип не найден", status_code=404)
    return templates.TemplateResponse(
        "material_types/detail.html",
        {"request": request, "user": user, "mt": mt, "back_to": back_to, "active_page": "material_types"},
    )


# --- Modules ---
@pages_router.get("/modules", response_class=HTMLResponse)
async def modules_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    per_page = await _get_per_page(session)
    items, prices, modules_data = await _sorted_modules(session)
    return templates.TemplateResponse(
        "modules/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "prices": prices,
            "attrs": {d["id"]: d for d in modules_data},
            "per_page": per_page,
            "total": len(items),
            "active_page": "modules",
        },
    )


@pages_router.post("/modules", response_class=HTMLResponse)
async def modules_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import ModuleCreateSchema

        await crud_modules.add_module(session, ModuleCreateSchema(name=name), created_by=user.name)
        await session.commit()
    return RedirectResponse("/reg/modules", status_code=302)


@pages_router.get("/modules/{mod_id}", response_class=HTMLResponse)
async def modules_detail_page(
    mod_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    mod = await crud_modules.get_module_by_id(session, mod_id)
    if not mod:
        return HTMLResponse("Модуль не найден", status_code=404)
    materials, _ = await crud_materials.get_materials(session, per_page=1000)
    all_modules, _ = await crud_modules.get_modules(session, per_page=1000)
    other_modules = [m for m in all_modules if m.id != mod_id]

    import json

    def _bom_flat(module, qty=1):
        result = []
        for item in module.items:
            if item.material:
                result.append(
                    {"name": item.material.name, "price": float(item.material.price), "quantity": item.quantity * qty}
                )
            elif item.sub_module:
                result.extend(_bom_flat(item.sub_module, item.quantity * qty))
        return result

    bom_items = _bom_flat(mod)
    bom_total = sum(bi["price"] * bi["quantity"] for bi in bom_items)
    prices = await crud_modules.get_module_prices(session)
    from scr.dbase import crud_nominal_currents

    nom_tok_values = await crud_nominal_currents.get_values(session)
    from scr.dbase import crud_material_types

    material_types, _ = await crud_material_types.get_all_types(session, per_page=10000)

    materials_json = json.dumps(
        [
            {
                "id": m.id,
                "name": m.name,
                "price": float(m.price),
                "type": m.type.name if m.type else "",
                "nom_tok": m.nom_tok,
                "voltage": m.voltage or "",
            }
            for m in materials
        ],
        ensure_ascii=False,
    )
    modules_json = json.dumps([{"id": m.id, "name": m.name} for m in other_modules], ensure_ascii=False)

    return templates.TemplateResponse(
        "modules/detail.html",
        {
            "request": request,
            "user": user,
            "mod": mod,
            "materials": materials,
            "modules": other_modules,
            "materials_json": materials_json,
            "modules_json": modules_json,
            "bom_items": bom_items,
            "bom_total": bom_total,
            "prices": prices,
            "nom_tok_values": nom_tok_values,
            "material_types": material_types,
            "back_to": back_to,
            "active_page": "modules",
        },
    )


# --- Contracts ---
@pages_router.get("/contracts", response_class=HTMLResponse)
async def contracts_list_page(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)

    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import selectinload

    from scr.dbase import crud_contract_specs
    from scr.dbase.models import ContractSpec, Organization

    per_page = await _get_per_page(session)

    # Count total
    count_stmt = sa_select(sa_func.count(ContractSpec.id))
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        sa_select(ContractSpec)
        .options(selectinload(ContractSpec.company))
        .options(selectinload(ContractSpec.request))
        .order_by(ContractSpec.contract_number, ContractSpec.specification_number)
    )
    result = await session.execute(stmt)
    specs = list(result.scalars().all())

    # Get all companies for filter dropdown
    all_companies_stmt = sa_select(Organization).order_by(Organization.name)
    companies_result = await session.execute(all_companies_stmt)
    companies = list(companies_result.scalars().all())

    return templates.TemplateResponse(
        "contracts/list.html",
        {
            "request": request,
            "user": user,
            "specs": specs,
            "companies": companies,
            "per_page": per_page,
            "total": total,
            "active_page": "contracts",
        },
    )


@pages_router.get("/requests/{req_id}/contracts", response_class=HTMLResponse)
async def request_contracts_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    if not req.company_id:
        return HTMLResponse("У ТКП не указана организация", status_code=400)

    from scr.dbase import crud_contract_specs

    specs = await crud_contract_specs.get_specs_by_company(session, req.company_id)
    await session.commit()

    return templates.TemplateResponse(
        "requests/contracts.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "specs": specs,
            "active_page": "requests",
        },
    )


# ==================== Накладные & ФОТ ====================


@pages_router.get("/nakladnye", response_class=HTMLResponse)
async def nakladnye_list_page(
    request: Request,
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase import crud_finance

    per_page = await _get_per_page(session)
    items, total = await crud_finance.get_invoice_items(session, page=page, per_page=per_page)
    # Resolve user names
    user_cache = {}
    items_with_user = []
    for item in items:
        uname = None
        if item.changed_by_id:
            if item.changed_by_id not in user_cache:
                u = await crud_users.get_user_by_id(session, item.changed_by_id)
                user_cache[item.changed_by_id] = u.name if u else str(item.changed_by_id)
            uname = user_cache[item.changed_by_id]
        items_with_user.append({"item": item, "user_name": uname})
    pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "finance/list.html",
        {
            "request": request,
            "user": user,
            "items": items_with_user,
            "total": total,
            "page": page,
            "pages": pages,
            "kind": "invoices",
            "kind_label": "Накладные",
            "active_page": "nakladnye",
        },
    )


@pages_router.get("/nakladnye/{item_id}", response_class=HTMLResponse)
async def nakladnye_detail_page(
    item_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase import crud_finance

    item = await crud_finance.get_invoice_item_by_id(session, item_id)
    if not item:
        return HTMLResponse("Запись не найдена", status_code=404)
    changed_by_name = None
    if item.changed_by_id:
        u = await crud_users.get_user_by_id(session, item.changed_by_id)
        changed_by_name = u.name if u else str(item.changed_by_id)
    return templates.TemplateResponse(
        "finance/detail.html",
        {
            "request": request,
            "user": user,
            "item": item,
            "changed_by_name": changed_by_name,
            "kind": "invoices",
            "kind_label": "Накладные",
            "active_page": "nakladnye",
        },
    )


@pages_router.get("/fot", response_class=HTMLResponse)
async def fot_list_page(
    request: Request,
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase import crud_finance

    per_page = await _get_per_page(session)
    items, total = await crud_finance.get_payroll_items(session, page=page, per_page=per_page)
    user_cache = {}
    items_with_user = []
    for item in items:
        uname = None
        if item.changed_by_id:
            if item.changed_by_id not in user_cache:
                u = await crud_users.get_user_by_id(session, item.changed_by_id)
                user_cache[item.changed_by_id] = u.name if u else str(item.changed_by_id)
            uname = user_cache[item.changed_by_id]
        items_with_user.append({"item": item, "user_name": uname})
    pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "finance/list.html",
        {
            "request": request,
            "user": user,
            "items": items_with_user,
            "total": total,
            "page": page,
            "pages": pages,
            "kind": "payroll",
            "kind_label": "ФОТ",
            "active_page": "fot",
        },
    )


@pages_router.get("/fot/{item_id}", response_class=HTMLResponse)
async def fot_detail_page(
    item_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    from scr.dbase import crud_finance

    item = await crud_finance.get_payroll_item_by_id(session, item_id)
    if not item:
        return HTMLResponse("Запись не найдена", status_code=404)
    changed_by_name = None
    if item.changed_by_id:
        u = await crud_users.get_user_by_id(session, item.changed_by_id)
        changed_by_name = u.name if u else str(item.changed_by_id)
    return templates.TemplateResponse(
        "finance/detail.html",
        {
            "request": request,
            "user": user,
            "item": item,
            "changed_by_name": changed_by_name,
            "kind": "payroll",
            "kind_label": "ФОТ",
            "active_page": "fot",
        },
    )
