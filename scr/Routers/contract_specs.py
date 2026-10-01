from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from scr.dbase import crud_contract_specs
from scr.dbase.database import db_helper
from scr.dbase.schemas.schemas import ContractSpecCreateSchema, ContractSpecResponseSchema

cs_router = APIRouter(prefix="/api/contract-specs", tags=["ContractSpecs"])


class ContractSpecUpdate(BaseModel):
    contract_number: int | None = None
    contract_date: str | None = None


@cs_router.get("/by-company/{company_id}", response_model=list[ContractSpecResponseSchema])
async def read_specs_by_company(company_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    return await crud_contract_specs.get_specs_by_company(session, company_id)


@cs_router.post("/", response_model=ContractSpecResponseSchema)
async def create_spec(
    data: ContractSpecCreateSchema,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    if data.new_contract:
        spec = await crud_contract_specs.add_new_contract(session, data.company_id, data.request_id)
    else:
        if not data.contract_number:
            raise HTTPException(status_code=400, detail="Укажите номер договора")
        spec = await crud_contract_specs.add_contract_spec(
            session, data.company_id, data.contract_number, data.request_id, data.contract_date
        )
    await session.commit()
    await session.refresh(spec, ["request"])
    return spec


@cs_router.patch("/{spec_id}", response_model=ContractSpecResponseSchema)
async def update_spec(
    spec_id: int,
    data: ContractSpecUpdate,
    session: AsyncSession = Depends(db_helper.session_dependency),
):
    from datetime import UTC, datetime

    contract_date = None
    if data.contract_date:
        try:
            contract_date = datetime.strptime(data.contract_date, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
    result = await crud_contract_specs.update_contract_spec(session, spec_id, data.contract_number, contract_date)
    if not result:
        raise HTTPException(status_code=404, detail="Спецификация не найдена")
    await session.commit()
    await session.refresh(result, ["request"])
    return result


@cs_router.delete("/{spec_id}")
async def delete_spec(spec_id: int, session: AsyncSession = Depends(db_helper.session_dependency)):
    if not await crud_contract_specs.delete_contract_spec(session, spec_id):
        raise HTTPException(status_code=404, detail="Спецификация не найдена")
    await session.commit()
    return {"message": "Удалено"}
