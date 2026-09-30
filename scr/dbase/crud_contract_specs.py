from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.dbase.models import ContractSpec


async def get_specs_by_company(session: AsyncSession, company_id: int) -> list[ContractSpec]:
    stmt = (
        select(ContractSpec)
        .where(ContractSpec.company_id == company_id)
        .options(selectinload(ContractSpec.request))
        .order_by(ContractSpec.contract_number, ContractSpec.specification_number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_next_contract_number(session: AsyncSession) -> int:
    stmt = select(func.coalesce(func.max(ContractSpec.contract_number), 0))
    result = await session.execute(stmt)
    return (result.scalar() or 0) + 1


async def get_next_spec_number(session: AsyncSession, contract_number: int) -> int:
    stmt = select(func.coalesce(func.max(ContractSpec.specification_number), 0)).where(
        ContractSpec.contract_number == contract_number
    )
    result = await session.execute(stmt)
    return (result.scalar() or 0) + 1


async def add_contract_spec(
    session: AsyncSession,
    company_id: int,
    contract_number: int,
    request_id: int | None = None,
    contract_date=None,
) -> ContractSpec:
    spec_number = await get_next_spec_number(session, contract_number)
    spec = ContractSpec(
        company_id=company_id,
        request_id=request_id,
        contract_number=contract_number,
        specification_number=spec_number,
    )
    if contract_date:
        spec.contract_date = contract_date
    session.add(spec)
    await session.flush()
    return spec


async def add_new_contract(
    session: AsyncSession,
    company_id: int,
    request_id: int | None = None,
) -> ContractSpec:
    contract_number = await get_next_contract_number(session)
    return await add_contract_spec(session, company_id, contract_number, request_id)


async def delete_contract_spec(session: AsyncSession, spec_id: int) -> bool:
    spec = await session.get(ContractSpec, spec_id)
    if spec:
        await session.delete(spec)
        await session.flush()
        return True
    return False
