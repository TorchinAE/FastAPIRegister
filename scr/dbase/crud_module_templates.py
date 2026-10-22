"""Шаблоны блоков раздела («по умолчанию»): модули обязательных строк и добавленные модули нового блока."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import DEFAULT_TEMPLATE_NAME
from scr.dbase.models import ModuleTypeDefault, ModuleTypeTemplate


async def get_templates(session: AsyncSession, module_type_id: int) -> list[ModuleTypeTemplate]:
    """Шаблоны раздела по порядку. Шаблонов нет — создаётся основной.
    Записи без шаблона (до шаблонов, старый API) переносятся в основной шаблон."""
    stmt = (
        select(ModuleTypeTemplate)
        .where(ModuleTypeTemplate.module_type_id == module_type_id)
        .options(selectinload(ModuleTypeTemplate.defaults).selectinload(ModuleTypeDefault.module))
        # Шаблон мог быть загружен раньше — состав перечитывается
        .execution_options(populate_existing=True)
        .order_by(ModuleTypeTemplate.sort_order, ModuleTypeTemplate.id)
    )
    templates = list((await session.execute(stmt)).scalars().all())
    orphans = ModuleTypeDefault.module_type_id == module_type_id, ModuleTypeDefault.template_id.is_(None)
    has_orphans = (await session.execute(select(ModuleTypeDefault.id).where(*orphans).limit(1))).first()
    if templates and not has_orphans:
        return templates
    if not templates:
        main = ModuleTypeTemplate(module_type_id=module_type_id, name=DEFAULT_TEMPLATE_NAME, sort_order=1)
        session.add(main)
        await session.flush()
    else:
        main = templates[0]
    if has_orphans:
        await session.execute(update(ModuleTypeDefault).where(*orphans).values(template_id=main.id))
        await session.flush()
    return list((await session.execute(stmt)).scalars().all())


async def get_template(session: AsyncSession, template_id: int) -> ModuleTypeTemplate | None:
    stmt = (
        select(ModuleTypeTemplate)
        .where(ModuleTypeTemplate.id == template_id)
        .options(selectinload(ModuleTypeTemplate.defaults).selectinload(ModuleTypeDefault.module))
        # Шаблон мог быть загружен раньше — состав перечитывается
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def resolve_template(
    session: AsyncSession, module_type_id: int, template_id: int | None
) -> ModuleTypeTemplate | None:
    """Шаблон раздела по id; не задан или чужой — основной (первый) шаблон раздела."""
    templates = await get_templates(session, module_type_id)
    return next((t for t in templates if t.id == template_id), templates[0] if templates else None)


async def add_template(
    session: AsyncSession,
    module_type_id: int,
    name: str,
    purpose: str | None = None,
    copy_from: int | None = None,
) -> ModuleTypeTemplate:
    """Новый шаблон; copy_from — скопировать модули другого шаблона того же раздела."""
    await get_templates(session, module_type_id)
    max_order = await session.execute(
        select(func.max(ModuleTypeTemplate.sort_order)).where(ModuleTypeTemplate.module_type_id == module_type_id)
    )
    tpl = ModuleTypeTemplate(
        module_type_id=module_type_id,
        name=name.strip() or DEFAULT_TEMPLATE_NAME,
        purpose=purpose or None,
        sort_order=(max_order.scalar() or 0) + 1,
    )
    session.add(tpl)
    await session.flush()
    source = await get_template(session, copy_from) if copy_from else None
    if source and source.module_type_id == module_type_id:
        for d in source.defaults:
            session.add(
                ModuleTypeDefault(
                    module_type_id=module_type_id,
                    template_id=tpl.id,
                    slot_id=d.slot_id,
                    module_id=d.module_id,
                    quantity=d.quantity,
                )
            )
        await session.flush()
    return await get_template(session, tpl.id)


async def update_template(
    session: AsyncSession, template_id: int, name: str | None = None, purpose: str | None = None, set_purpose=False
) -> ModuleTypeTemplate | None:
    tpl = await session.get(ModuleTypeTemplate, template_id)
    if not tpl:
        return None
    if name is not None and name.strip():
        tpl.name = name.strip()
    if set_purpose:
        tpl.purpose = purpose or None
    await session.flush()
    return tpl


async def delete_template(session: AsyncSession, template_id: int) -> ModuleTypeTemplate | None:
    """Удаляет шаблон вместе с его модулями. Последний шаблон раздела не удаляется (ValueError)."""
    tpl = await session.get(ModuleTypeTemplate, template_id)
    if not tpl:
        return None
    count = await session.execute(
        select(func.count(ModuleTypeTemplate.id)).where(ModuleTypeTemplate.module_type_id == tpl.module_type_id)
    )
    if (count.scalar() or 0) <= 1:
        raise ValueError("Нельзя удалить последний шаблон раздела")
    await session.delete(tpl)
    await session.flush()
    return tpl


async def add_template_item(
    session: AsyncSession, tpl: ModuleTypeTemplate, module_id: int, quantity: int
) -> ModuleTypeDefault:
    """Модуль шаблона вне обязательных строк; уже есть — увеличивается количество."""
    stmt = select(ModuleTypeDefault).where(
        ModuleTypeDefault.template_id == tpl.id,
        ModuleTypeDefault.module_id == module_id,
        ModuleTypeDefault.slot_id.is_(None),
    )
    obj = (await session.execute(stmt)).scalars().first()
    if obj:
        obj.quantity += quantity
    else:
        obj = ModuleTypeDefault(
            module_type_id=tpl.module_type_id, template_id=tpl.id, module_id=module_id, quantity=quantity
        )
        session.add(obj)
    await session.flush()
    return obj


def template_json(tpl: ModuleTypeTemplate, slots: list, prices: dict[int, float]) -> dict:
    """Шаблон для страницы «по умолчанию»: модули обязательных строк и добавленные модули."""
    known = {s.id for s in slots}
    by_slot = {d.slot_id: d for d in tpl.defaults if d.slot_id in known}
    return {
        "id": tpl.id,
        "name": tpl.name,
        "purpose": tpl.purpose or "",
        "slots": {
            s.id: {"module_id": by_slot[s.id].module_id, "quantity": by_slot[s.id].quantity}
            for s in slots
            if s.id in by_slot
        },
        "items": [
            {
                "id": d.id,
                "module_id": d.module_id,
                "module_name": d.module.name if d.module else "?",
                "quantity": d.quantity,
                "module_price": prices.get(d.module_id, 0.0),
            }
            for d in tpl.defaults
            if d.slot_id not in known
        ],
    }
