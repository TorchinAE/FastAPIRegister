from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase.database import db_helper
from scr.dbase import crud_users, crud_requests, crud_counterparties
from scr.dbase import crud_organizations, crud_directors, crud_positions, crud_equipment, crud_invoices, crud_settings, crud_payments
from scr.dbase.models import Probability, Manager
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
    response = RedirectResponse("/requests", status_code=302)
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
    response = RedirectResponse("/requests", status_code=302)
    response.set_cookie(key=SESSION_KEY, value=user.email, httponly=True)
    return response


@pages_router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
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
        return RedirectResponse("/", status_code=302)
    requests_list, total = await crud_requests.get_requests(session, page=page)
    per_page = 20
    pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "requests/list.html",
        {"request": request, "user": user, "items": requests_list, "page": page, "pages": pages, "total": total,
         "statuses": RequestStatus, "active_page": "requests"},
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
    equipment_list, _ = await crud_equipment.get_equipment_list(session, per_page=100)
    return templates.TemplateResponse(
        "requests/create.html",
        {"request": request, "user": user, "counterparties": cps, "equipment": equipment_list, "statuses": RequestStatus, "active_page": "requests"},
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

    # Find manager by user email
    mgr, _ = await crud_users.get_users(session, search=user.email, per_page=1)
    manager_id = mgr[0].id if mgr else 1

    schema = RequestCreateSchema(**data)
    await crud_requests.add_request(session, schema, manager_id=manager_id, created_by=user.name, user_city=user.city)
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
        return HTMLResponse("ТКП не найдена", status_code=404)
    return templates.TemplateResponse(
        "requests/detail.html",
        {"request": request, "user": user, "req": req, "active_page": "requests"},
    )


@pages_router.get("/requests/{req_id}/edit", response_class=HTMLResponse)
async def request_edit_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    cps, _ = await crud_counterparties.get_counterparties(session, per_page=100)
    managers_list, _ = await crud_users.get_users(session, per_page=100)
    equipment_list, _ = await crud_equipment.get_equipment_list(session, per_page=100)
    companies_list, _ = await crud_organizations.get_organizations(session, per_page=100)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select as sa_select
    mgr_result = await session.execute(
        sa_select(Manager).options(selectinload(Manager.organizations)).order_by(Manager.name)
    )
    managers_with_orgs = list(mgr_result.scalars().all())
    related, _ = await crud_requests.get_requests(session, company_id=req.company_id, per_page=50)
    invoices = await crud_invoices.get_invoices_by_request(session, req_id)
    payment_items = await crud_payments.ensure_payment_items(session, req_id)
    all_settings = await crud_settings.get_all_settings(session)
    settings_dict = {s.key: s.value for s in all_settings}
    probs_result = await session.execute(sa_select(Probability).order_by(Probability.id))
    probabilities = list(probs_result.scalars().all())
    return templates.TemplateResponse(
        "requests/edit.html",
        {"request": request, "user": user, "req": req, "counterparties": cps, "managers": managers_list, "managers_with_orgs": managers_with_orgs, "equipment": equipment_list, "companies": companies_list, "related_requests": related, "statuses": RequestStatus, "invoices": invoices, "payment_items": payment_items, "settings": settings_dict, "probabilities": probabilities, "active_page": "requests"},
    )


@pages_router.post("/requests/{req_id}/edit", response_class=HTMLResponse)
async def request_edit_submit(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    from scr.dbase.schemas.schemas import RequestUpdateSchema

    data = {"id": req_id}
    if form.get("counterparty_id"):
        data["counterparty_id"] = int(form["counterparty_id"])
    if form.get("company_id"):
        data["company_id"] = int(form["company_id"])
    if form.get("contact_id"):
        data["manager_id"] = int(form["contact_id"])
    elif form.get("manager_id"):
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
    return RedirectResponse(f"/requests/{req_id}/edit", status_code=302)


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
    companies, _ = await crud_organizations.get_organizations(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "counterparties/list.html",
        {"request": request, "user": user, "items": items, "companies": companies, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "counterparties", "statuses": RequestStatus},
    )


@pages_router.post("/counterparties", response_class=HTMLResponse)
async def counterparties_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
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
    return RedirectResponse("/counterparties", status_code=302)


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
    managers_list, _ = await crud_users.get_users(session, per_page=100)
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
    directors, _ = await crud_directors.get_dirs(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "companies/list.html",
        {"request": request, "user": user, "items": items, "directors": directors, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "companies"},
    )


@pages_router.post("/companies", response_class=HTMLResponse)
async def companies_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import OrganizationAddSchema
        data = {
            "name": name,
            "inn": form.get("inn") or None,
            "address": form.get("address") or None,
            "director_id": int(form["director_id"]),
        }
        await crud_organizations.add_organization(session, OrganizationAddSchema(**data), created_by=user.name)
        await session.commit()
    return RedirectResponse("/companies", status_code=302)


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
    managers_list, _ = await crud_users.get_users(session, per_page=100)
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
    managers_list, _ = await crud_users.get_users(session, per_page=100)
    reqs, _ = await crud_requests.get_requests(session, company_id=org_id, per_page=100)
    return templates.TemplateResponse(
        "companies/edit.html",
        {"request": request, "user": user, "org": org, "directors": directors, "all_managers": managers_list, "reqs": reqs, "back_to": back_to, "active_page": "companies"},
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
        return RedirectResponse("/", status_code=302)
    items, total = await crud_users.get_users(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "users/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "users"},
    )


@pages_router.post("/users", response_class=HTMLResponse)
async def users_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    email = form.get("email", "").strip()
    if name and email:
        existing = await crud_users.get_user_by_email(session, email)
        if not existing:
            from scr.dbase.schemas.schemas import UserCreate
            await crud_users.create_user(session, UserCreate(name=name, email=email, password="123456", city=form.get("city", "ив").strip() or "ив", signature=form.get("signature") or None))
            await session.commit()
    return RedirectResponse("/users", status_code=302)


@pages_router.get("/users/{user_id}", response_class=HTMLResponse)
async def users_detail_page(
    user_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    target = await crud_users.get_user_by_id(session, user_id)
    if not target:
        return HTMLResponse("Пользователь не найден", status_code=404)
    return templates.TemplateResponse(
        "users/detail.html",
        {"request": request, "user": user, "target": target, "back_to": back_to, "active_page": "users"},
    )


@pages_router.delete("/users/{user_id}/delete")
async def users_delete(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return JSONResponse({"error": "Не авторизован"}, status_code=401)
    result = await crud_users.delete_user(session, user_id)
    if not result:
        return JSONResponse({"error": "Пользователь не найден"}, status_code=404)
    await session.commit()
    return JSONResponse({"ok": True})


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
    positions, _ = await crud_positions.get_all_positions(session, per_page=100)
    per_page = 20
    return templates.TemplateResponse(
        "directors/list.html",
        {"request": request, "user": user, "items": items, "positions": positions, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "directors"},
    )


@pages_router.post("/directors", response_class=HTMLResponse)
async def directors_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
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
    return RedirectResponse("/directors", status_code=302)


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
        return RedirectResponse("/", status_code=302)
    items, total = await crud_positions.get_all_positions(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "positions/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "positions"},
    )


@pages_router.post("/positions", response_class=HTMLResponse)
async def positions_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import PositionCreateSchema
        await crud_positions.add_position(session, PositionCreateSchema(name=name), created_by=user.name)
        await session.commit()
    return RedirectResponse("/positions", status_code=302)


@pages_router.get("/positions/{pos_id}", response_class=HTMLResponse)
async def positions_detail_page(
    pos_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
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
        return RedirectResponse("/", status_code=302)
    items, total = await crud_equipment.get_equipment_list(session, page=page)
    per_page = 20
    return templates.TemplateResponse(
        "equipment/list.html",
        {"request": request, "user": user, "items": items, "page": page, "pages": (total + per_page - 1) // per_page, "total": total, "active_page": "equipment"},
    )


@pages_router.post("/equipment", response_class=HTMLResponse)
async def equipment_create_submit(
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    form = await request.form()
    name = form.get("name", "").strip()
    if name:
        from scr.dbase.schemas.schemas import EquipmentCreateSchema
        await crud_equipment.add_equipment(session, EquipmentCreateSchema(name=name), created_by=user.name)
        await session.commit()
    return RedirectResponse("/equipment", status_code=302)


@pages_router.get("/equipment/{eq_id}", response_class=HTMLResponse)
async def equipment_detail_page(
    eq_id: int,
    request: Request,
    back_to: str | None = None,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    eq = await crud_equipment.get_equipment_by_id(session, eq_id)
    if not eq:
        return HTMLResponse("Оборудование не найдено", status_code=404)
    return templates.TemplateResponse(
        "equipment/detail.html",
        {"request": request, "user": user, "eq": eq, "back_to": back_to, "active_page": "equipment"},
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
        return RedirectResponse("/", status_code=302)
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
        return RedirectResponse("/", status_code=302)
    from sqlalchemy import select, func, join
    from sqlalchemy.orm import selectinload
    from scr.dbase.models import Invoice, Request as ReqModel

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
        {"request": request, "user": user, "items": items, "page": page, "pages": pages, "total": total, "active_page": "invoices"},
    )


@pages_router.get("/requests/{req_id}/calc", response_class=HTMLResponse)
async def request_calc_page(
    req_id: int,
    request: Request,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    user = await get_current_user(request, session)
    if not user:
        return RedirectResponse("/", status_code=302)
    req = await crud_requests.get_request_by_id(session, req_id)
    if not req:
        return HTMLResponse("ТКП не найдена", status_code=404)
    return templates.TemplateResponse(
        "requests/calc.html",
        {"request": request, "user": user, "req": req, "active_page": "requests"},
    )
