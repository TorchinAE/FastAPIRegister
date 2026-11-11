"""Данные договора и спецификации для Word (scr/utils/contract_docx.py) по записи ContractSpec и её ТКП."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from scr.constants import CONTRACT_TEMPLATE, SPECIFICATION_TEMPLATE
from scr.dbase import crud_module_slots, crud_module_types, crud_requests, crud_settings
from scr.dbase.crud_module_types import WORKS_SECTIONS
from scr.dbase.models import ContractSpec, Delivery, Directors, Organization, PaymentItem
from scr.utils.contract_docx import (
    ContractData,
    Party,
    SpecData,
    SpecPayment,
    SpecRow,
    build_contract_docx,
    build_spec_docx,
    safe_file_name,
)
from scr.utils.declension import fio_genitive, initials_signature, is_female, position_genitive
from scr.utils.doc_templates import read_template
from scr.utils.num_words import date_words, money, rubles_in_words


async def _company(session: AsyncSession, company_id: int) -> Organization | None:
    stmt = (
        select(Organization)
        .where(Organization.id == company_id)
        .options(selectinload(Organization.director).selectinload(Directors.position))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _party(company: Organization | None) -> Party:
    if not company:
        return Party()
    director = company.director
    fio = director.name if director else ""
    return Party(
        name=company.name or "",
        full_name=company.full_name or "",
        director_position=position_genitive(director.position.name) if director and director.position else "",
        director_name=fio_genitive(fio) if fio else "",
        acting="действующей" if fio and is_female(fio) else "действующего",
        basis=company.basis or "Устава",
        requisites=company.requisites or "",
        signature=initials_signature(fio) if fio else "",
    )


def contract_file_name(spec: ContractSpec, company: Organization | None) -> str:
    org = company.name if company else ""
    return safe_file_name(f"Договор №{spec.contract_number} {org}") + ".docx"


def spec_file_name(spec: ContractSpec, company: Organization | None) -> str:
    org = company.name if company else ""
    name = f"Спецификация №{spec.specification_number} к договору №{spec.contract_number} {org}"
    return safe_file_name(name) + ".docx"


async def build_contract(session: AsyncSession, spec: ContractSpec) -> tuple[bytes, str]:
    """Договор в Word: (содержимое, имя файла)."""
    company = await _company(session, spec.company_id)
    year = (spec.contract_date or datetime.now()).year
    data = ContractData(
        number=str(spec.contract_number),
        date=date_words(spec.contract_date),
        next_year=str(year + 1),
        party=_party(company),
    )
    content = build_contract_docx(await read_template(session, CONTRACT_TEMPLATE), data)
    return content, contract_file_name(spec, company)


async def build_specification(session: AsyncSession, spec: ContractSpec) -> tuple[bytes, str]:
    """Спецификация в Word по комплектации ТКП спецификации: (содержимое, имя файла)."""
    from scr.dbase.crud_tkp import build_tkp_kit

    company = await _company(session, spec.company_id)
    nds_val = await crud_settings.get_setting(session, "nds_percent")
    nds_percent = float(nds_val) if nds_val else 20.0

    rows: list[SpecRow] = []
    services: list[str] = []
    delivery_address = ""
    pay_items: list[PaymentItem] = []
    total = 0.0
    req = await crud_requests.get_request_by_id(session, spec.request_id) if spec.request_id else None
    if req:
        await crud_module_slots.sync_hidden_slots(session, req.id)
        await crud_module_types.sync_mounting(session, req.id)
        await session.commit()
        for section in await build_tkp_kit(session, req):
            if section["slug"] in WORKS_SECTIONS:
                services.append(section["name"])
            if section["header"]:
                rows.append(SpecRow(f"{section['name']} в составе:"))
            for block in section["blocks"]:
                rows.append(SpecRow(block["title"], list(block["lines"]), block["quantity"], block["sum"]))
                total += block["sum"]
        delivery = (await session.execute(select(Delivery).where(Delivery.request_id == req.id))).scalars().first()
        if delivery and float(delivery.final_price or 0) > 0:
            delivery_address = (delivery.address or "").strip() or "адреса Покупателя"
        pay_stmt = select(PaymentItem).where(PaymentItem.request_id == req.id).order_by(PaymentItem.id)
        pay_items = [p for p in (await session.execute(pay_stmt)).scalars().all() if float(p.percent or 0)]

    total_nds = total * (1 + nds_percent / 100)
    payments = [SpecPayment(float(p.percent), rubles_in_words(total_nds * float(p.percent) / 100)) for p in pay_items]
    data = SpecData(
        number=str(spec.specification_number),
        date=date_words(spec.specification_date or spec.contract_date),
        contract_number=str(spec.contract_number),
        contract_date=date_words(spec.contract_date),
        party=_party(company),
        rows=rows,
        total=money(total),
        nds_percent=nds_percent,
        nds=money(total_nds - total),
        total_nds=money(total_nds),
        delivery_term=date_words(None),
        payments=payments,
        services=(", ".join(services) + " — входят в стоимость Спецификации.") if services else "не предусмотрены.",
        delivery_address=delivery_address,
    )
    content = build_spec_docx(await read_template(session, SPECIFICATION_TEMPLATE), data)
    return content, spec_file_name(spec, company)
