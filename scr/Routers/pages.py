from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import (
    crud_counterparties,
    crud_directors,
    crud_equipment,
    crud_invoices,
    crud_material_types,
    crud_materials,
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
                    "error": f"Регистрация только с домена @{app_settings.MY_DOMEN}",
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


@pages_router.get("/logout")
async def logout():
    response = RedirectResponse("/reg/", status_code=302)
    response.delete_cookie(key=SESSION_KEY)
    return response


# --- Requests ---
@pages_router.get("/requests", response_class=HTMLResponse)
async def requests_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    requests_list, total = await crud_requests.get_requests(session, page=page)
    per_page = 20
    pages = (total + per_page - 1) // per_page

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
            "page": page,
            "pages": pages,
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
    return RedirectResponse(f"/requests/{new_req.id}", status_code=302)


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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_counterparties.get_counterparties(session, page=page)
    companies, _ = await crud_organizations.get_organizations(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "counterparties/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "companies": companies,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_organizations.get_organizations(session, page=page)
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "companies/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "directors": directors,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_users.get_users(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "users/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_directors.get_dirs(session, page=page)
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "directors/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "positions": positions,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_positions.get_all_positions(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "positions/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_equipment.get_equipment_list(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "equipment/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
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
    per_page = 20
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(stmt)
    items = list(result.scalars().all())
    pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "invoices/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": pages,
            "total": total,
            "active_page": "invoices",
        },
    )


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

    if adres_server and req.company:
        year = req.request_date.year if req.request_date else 2025
        slug = req.company.server_address_slug or "default"
        org_name = (
            (req.company.name or "Unknown")
            .replace(" ", "_")
            .replace('"', "")
            .replace("'", "")
            .replace("/", "_")
            .replace("\\", "_")
        )
        folder_path = os.path.join(
            adres_server, "01_\u0422\u041a\u041f", f"01_\u0422\u041a\u041f_{year}", slug, f"{req.id}_{org_name}"
        )
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

    return templates.TemplateResponse(
        "requests/calc.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "folder_path": folder_path or "",
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
        return HTMLResponse(
            "\u0422\u041a\u041f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", status_code=404
        )
    materials, _ = await crud_materials.get_materials(session, per_page=1000)
    modules_list, _ = await crud_modules.get_modules(session, per_page=1000)

    import json

    def _mod_items_json(mod):
        items = []
        for item in mod.items:
            if item.material:
                items.append(
                    {
                        "material": {"name": item.material.name, "price": float(item.material.price)},
                        "quantity": item.quantity,
                    }
                )
        return items

    modules_json = json.dumps(
        [{"id": m.id, "name": m.name, "total_price": m.total_price, "items": _mod_items_json(m)} for m in modules_list],
        ensure_ascii=False,
    )
    materials_json = json.dumps(
        [{"id": m.id, "name": m.name, "price": float(m.price)} for m in materials], ensure_ascii=False
    )

    return templates.TemplateResponse(
        "requests/calc_tkp.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "modules": modules_list,
            "materials": materials,
            "modules_json": modules_json,
            "materials_json": materials_json,
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


SERVICE_SECTIONS = {
    "chief-engineer": ("Шеф-инженер", "chief_engineer_cost"),
    "smr": ("СМР", "smr_cost"),
    "pnr": ("ПНР", "pnr_cost"),
}


@pages_router.get("/requests/{req_id}/calc/{section}", response_class=HTMLResponse)
async def request_calc_page_by_section(
    req_id: int,
    section: str,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    if section in ("tkp", "delivery"):
        return RedirectResponse(f"/reg/requests/{req_id}/calc/{section}", status_code=302)
    if section not in SERVICE_SECTIONS:
        return await request_calc_stub_page(req_id, section, request, session)
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    from scr.dbase import crud_service_calcs

    label, cost_field = SERVICE_SECTIONS[section]
    calc = await crud_service_calcs.get_or_create_service_calc(session, req_id, section)
    await session.commit()
    # Use company profitability as default
    profitability = float(req.company.profitability) if req.company and req.company.profitability else 15.0
    if calc.profitability_percent and float(calc.profitability_percent) > 0:
        profitability = float(calc.profitability_percent)
    return templates.TemplateResponse(
        "requests/calc_service.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "calc": calc,
            "section": section,
            "section_label": label,
            "cost_field": cost_field,
            "profitability": profitability,
            "active_page": "requests",
        },
    )


STUB_SECTIONS = {
    "corpusa": "\u041a\u043e\u0440\u043f\u0443\u0441\u0430",
    "kso": "\u041a\u0421\u041e",
    "kru": "\u041a\u0420\u0423",
    "sho": "\u0429\u041e",
    "ktp": "\u041a\u0422\u041f",
    "pku": "\u041f\u041a\u0423",
    "pus": "\u041f\u0423\u0421",
}


async def request_calc_stub_page(
    req_id: int,
    section: str,
    request: Request,
    session: AsyncSession,
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse(
            "\u0422\u041a\u041f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430", status_code=404
        )
    section_name = STUB_SECTIONS.get(section, section)
    return templates.TemplateResponse(
        "requests/calc_stub.html",
        {
            "request": request,
            "user": user,
            "req": req,
            "section": section,
            "section_name": section_name,
            "active_page": "requests",
        },
    )


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
    per_page_str = await crud_settings.get_setting(session, "materials_per_page")
    per_page = int(per_page_str) if per_page_str else 30

    # Build set of material names that have modules
    from scr.dbase import crud_modules

    all_modules = await crud_modules.get_all_modules(session)
    module_names = {m.name for m in all_modules}

    await session.commit()
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
    return templates.TemplateResponse(
        "materials/detail.html",
        {"request": request, "user": user, "mat": mat, "types": types, "back_to": back_to, "active_page": "materials"},
    )


# --- Material Types ---
@pages_router.get("/material-types", response_class=HTMLResponse)
async def material_types_page(
    request: Request,
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_material_types.get_all_types(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "material_types/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
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
    page: int = 1,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/reg/", status_code=302)
    items, total = await crud_modules.get_modules(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "modules/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "page": page,
            "pages": (total + per_page - 1) // per_page,
            "total": total,
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

    materials_json = json.dumps(
        [{"id": m.id, "name": m.name, "price": float(m.price)} for m in materials], ensure_ascii=False
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

    from sqlalchemy import select as sa_select
    from sqlalchemy.orm import selectinload

    from scr.dbase import crud_contract_specs
    from scr.dbase.models import ContractSpec, Organization

    stmt = (
        sa_select(ContractSpec)
        .options(selectinload(ContractSpec.company))
        .options(selectinload(ContractSpec.request))
        .order_by(ContractSpec.contract_number, ContractSpec.specification_number)
    )
    result = await session.execute(stmt)
    all_specs = list(result.scalars().all())

    # Get unique companies for filter
    companies_set = {}
    for spec in all_specs:
        if spec.company_id not in companies_set:
            companies_set[spec.company_id] = spec.company

    return templates.TemplateResponse(
        "contracts/list.html",
        {
            "request": request,
            "user": user,
            "specs": all_specs,
            "companies": list(companies_set.values()),
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

    items, total = await crud_finance.get_invoice_items(session, page=page, per_page=50)
    pages = (total + 49) // 50
    return templates.TemplateResponse(
        "finance/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
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
    return templates.TemplateResponse(
        "finance/detail.html",
        {
            "request": request,
            "user": user,
            "item": item,
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

    items, total = await crud_finance.get_payroll_items(session, page=page, per_page=50)
    pages = (total + 49) // 50
    return templates.TemplateResponse(
        "finance/list.html",
        {
            "request": request,
            "user": user,
            "items": items,
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
    return templates.TemplateResponse(
        "finance/detail.html",
        {
            "request": request,
            "user": user,
            "item": item,
            "kind": "payroll",
            "kind_label": "ФОТ",
            "active_page": "fot",
        },
    )
