from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_calc_products
from scr.dbase.schemas.schemas import (
    CalcProductCreateSchema, CalcProductUpdateSchema,
    CalcProductResponseSchema, CalcProductDetailSchema, PaginatedResponse,
)

cp_router = APIRouter(prefix="/api/calc-products", tags=["Calc Products"])


@cp_router.get("/", response_model=PaginatedResponse)
async def list_products(
    section_id: int | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    items, total = await crud_calc_products.get_products(session, section_id, search, page, per_page)
    return PaginatedResponse(
        items=[CalcProductResponseSchema(
            id=p.id, name=p.name, section_id=p.section_id,
            section_name=p.section.name if p.section else None,
            is_composite=len(p.components) > 0 if hasattr(p, 'components') and p.components else False,
            created_by=p.created_by,
        ) for p in items],
        total=total, page=page, per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@cp_router.get("/{product_id}", response_model=CalcProductDetailSchema)
async def get_product(product_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    product = await crud_calc_products.get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return CalcProductDetailSchema(
        id=product.id, name=product.name, section_id=product.section_id,
        section_name=product.section.name if product.section else None,
        components=[{
            "id": c.id, "equipment_id": c.equipment_id,
            "equipment_name": c.equipment.name if c.equipment else "?",
            "quantity": c.quantity,
        } for c in product.components],
        created_by=product.created_by,
    )


@cp_router.post("/", response_model=CalcProductResponseSchema)
async def create_product(
    data: CalcProductCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    product = await crud_calc_products.add_product(session, data)
    await session.commit()
    return CalcProductResponseSchema(
        id=product.id, name=product.name, section_id=product.section_id,
        is_composite=len(data.components) > 0, created_by=product.created_by,
    )


@cp_router.put("/{product_id}", response_model=CalcProductResponseSchema)
async def update_product(
    product_id: int, data: CalcProductUpdateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    data.id = product_id
    product = await crud_calc_products.update_product(session, data)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await session.commit()
    return CalcProductResponseSchema(
        id=product.id, name=product.name, section_id=product.section_id,
        is_composite=len(product.components) > 0, created_by=product.created_by,
    )


@cp_router.delete("/{product_id}")
async def delete_product(product_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_calc_products.delete_product(session, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    await session.commit()
    return {"ok": True}


@cp_router.get("/{product_id}/expand")
async def expand_product(
    product_id: int, quantity: int = Query(1, ge=1),
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    return await crud_calc_products.expand_product(session, product_id, quantity)
