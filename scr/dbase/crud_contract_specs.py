import os
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import SETTING_CONTRACT_FOLDER
from scr.dbase import crud_settings
from scr.dbase.models import ContractSpec


def folder_safe_name(name: str) -> str:
    """Название для имени папки: без кавычек, пробелы и недопустимые в Windows символы — «_» (как у папки ТКП)."""
    return re.sub(r"[\s/\\:*?<>|]+", "_", re.sub(r"[\"']", "", name)).strip("_") or "Unknown"


def contract_folder_path(base: str, spec: ContractSpec) -> str | None:
    """Папка договора: {contract_folder}/{номер договора}_{организация}. Все спецификации договора — в ней."""
    if not base:
        return None
    org = folder_safe_name(spec.company.name if spec.company else "Unknown")
    return base.rstrip("/\\") + "/" + f"{spec.contract_number}_{org}"


async def ensure_contract_folder(session: AsyncSession, spec: ContractSpec) -> tuple[str | None, bool]:
    """Путь папки договора и удалось ли её создать (папка может быть недоступна с сервера)."""
    base = await crud_settings.get_setting(session, SETTING_CONTRACT_FOLDER) or ""
    path = contract_folder_path(base, spec)
    if not path:
        return None, False
    try:
        os.makedirs(path, exist_ok=True)
        return path, True
    except OSError:
        return path, False


async def get_spec_by_id(session: AsyncSession, spec_id: int) -> ContractSpec | None:
    stmt = select(ContractSpec).where(ContractSpec.id == spec_id).options(selectinload(ContractSpec.company))
    return (await session.execute(stmt)).scalar_one_or_none()


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


async def update_contract_spec(
    session: AsyncSession,
    spec_id: int,
    contract_number: int | None = None,
    contract_date=None,
) -> ContractSpec | None:
    spec = await session.get(ContractSpec, spec_id)
    if not spec:
        return None
    if contract_number is not None:
        spec.contract_number = contract_number
    if contract_date is not None:
        spec.contract_date = contract_date
    await session.flush()
    return spec


async def delete_contract_spec(session: AsyncSession, spec_id: int) -> bool:
    spec = await session.get(ContractSpec, spec_id)
    if spec:
        await session.delete(spec)
        await session.flush()
        return True
    return False
