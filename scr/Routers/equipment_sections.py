from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from scr.dbase.database import db_helper
from scr.dbase import crud_equipment_sections
from scr.dbase.schemas.schemas import EquipmentSectionCreateSchema, EquipmentSectionUpdateSchema, EquipmentSectionResponseSchema

es_router = APIRouter(prefix="/api/equipment-sections", tags=["Equipment Sections"])


@es_router.get("/", response_model=list[EquipmentSectionResponseSchema])
async def list_sections(session: AsyncSession = Depends(db_helper.session_dependency)):
    items, _ = await crud_equipment_sections.get_all_sections(session, per_page=100)
    return items


@es_router.get("/{section_id}", response_model=EquipmentSectionResponseSchema)
async def get_section(section_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    section = await crud_equipment_sections.get_section_by_id(session, section_id)
    if not section:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Не найдено"}, status_code=404)
    return section


@es_router.post("/", response_model=EquipmentSectionResponseSchema)
async def create_section(schema: EquipmentSectionCreateSchema, session: AsyncSession = Depends(db_helper.session_dependency)):
    section = await crud_equipment_sections.add_section(session, schema)
    await session.commit()
    return section


@es_router.put("/{section_id}", response_model=EquipmentSectionResponseSchema)
async def update_section(section_id: int, schema: EquipmentSectionUpdateSchema, session: AsyncSession = Depends(db_helper.session_dependency)):
    schema.id = section_id
    section = await crud_equipment_sections.update_section(session, schema)
    if not section:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Не найдено"}, status_code=404)
    await session.commit()
    return section


@es_router.delete("/{section_id}")
async def delete_section(section_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    result = await crud_equipment_sections.delete_section(session, section_id)
    if not result:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Не найдено"}, status_code=404)
    await session.commit()
    return {"ok": True}
