# models.py
import enum
from datetime import UTC, datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def split_name(input_name: str) -> dict:
    parts = input_name.split(None, 2)
    for x in range(len(parts)):
        parts[x] = parts[x].title().strip()
    keys = ["last_name", "name", "patronymic"]
    return dict(zip(keys, parts))


def get_short_name(input_name: str) -> str:
    names = split_name(input_name)
    return (
        f"{names.get('last_name')}"
        f"{' ' + names.get('name')[0] + '.' if names.get('name') else ''}"
        f"{' ' + names.get('patronymic')[0] + '.' if names.get('patronymic') else ''}"
    )


def get_give_name(input_name: str) -> str:
    spl_name = split_name(input_name)
    result = ""

    name = spl_name.get("name")
    if name:
        if name[-1] == "й":
            result += name[:-1] + "ю"
        else:
            result += name + "у"

    patronymic = spl_name.get("patronymic")
    if patronymic:
        if patronymic[-1] == "ч":
            result += " " + patronymic + "у"
        else:
            result += " " + patronymic
    return result


class RequestStatus(str, enum.Enum):
    ZAPROS = "запрос"
    TENDER = "тендер"
    NOT_ACTUAL = "не актуально"
    DOC_PROCESSING = "оформление документов"
    DOC_SIGNING = "подписание документов"
    WAITING_PAYMENT = "ожидание оплаты"
    ORDER = "заказ"


class Base(DeclarativeBase):
    pass


class BaseID(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(50), nullable=False, default="ив")
    signature: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class Organization(BaseID):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inn: Mapped[str] = mapped_column(String(12), unique=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    server_address_slug: Mapped[str] = mapped_column(String(200), nullable=False, default="/02_сторонние_заказчики")
    director_id: Mapped[int] = mapped_column(ForeignKey("directors.id"), nullable=False)

    director: Mapped["Directors"] = relationship(back_populates="organizations")
    counterparties: Mapped[list["Counterparty"]] = relationship(back_populates="company")

    def __repr__(self) -> str:
        director_name = self.director.name if self.director else "None"
        return (
            f"Organization(id={self.id}, "
            f"name='{self.name}', "
            f"inn='{self.inn}', "
            f"director='{director_name}', "
            f"address='{self.address}')"
        )


class Directors(BaseID):
    __tablename__ = "directors"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))

    position: Mapped["Positions"] = relationship(back_populates="directors")
    organizations: Mapped[list["Organization"]] = relationship(back_populates="director")

    @property
    def short_name(self) -> str:
        return get_short_name(self.name)

    @property
    def give_name(self) -> str:
        return get_give_name(self.name)

    def __repr__(self) -> str:
        org_names = [org.name for org in self.organizations] if self.organizations else []
        return (
            f"Director(id={self.id}, "
            f"name='{self.name}', "
            f"position='{self.position}', "
            f"email='{self.email}', "
            f"phone='{self.phone}', "
            f"organizations={org_names})"
        )


class Positions(BaseID):
    __tablename__ = "positions"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    directors: Mapped[list["Directors"]] = relationship(back_populates="position")

    def __repr__(self) -> str:
        return f"Positions(id={self.id}, name='{self.name}')"


class Counterparty(BaseID):
    __tablename__ = "counterparties"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)

    company: Mapped["Organization"] = relationship(back_populates="counterparties")


class Equipment(BaseID):
    __tablename__ = "equipment"
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"Equipment(id={self.id}, name='{self.name}')"


class Probability(Base):
    __tablename__ = "probabilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"Probability(id={self.id}, name='{self.name}', value={self.value})"


DEFAULT_PROBABILITIES = [
    (1, "30%", 30),
    (2, "50%", 50),
    (3, "80%", 80),
    (4, "95%", 95),
    (5, "100%", 100),
]


class Request(BaseID):
    __tablename__ = "requests"
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), nullable=True)
    probability_id: Mapped[int | None] = mapped_column(ForeignKey("probabilities.id"), nullable=True)
    project_stamp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    issue_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.ZAPROS, nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tkp_num: Mapped[str | None] = mapped_column(String(50), nullable=True)
    incoming_letter_num: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repeat_tkp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_num: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    factory_order_num: Mapped[str | None] = mapped_column(String(100), nullable=True)
    factory_order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ship_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Оборудование (количество, 0-100)
    bktpb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ktpb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ktp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kso_393: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kso_204: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    k_104: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    k_104m: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sho: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pku: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    counterparty: Mapped["Counterparty"] = relationship(foreign_keys=[counterparty_id])
    company: Mapped["Organization"] = relationship(foreign_keys=[company_id])
    manager: Mapped["User"] = relationship(foreign_keys=[manager_id])
    equipment: Mapped[Optional["Equipment"]] = relationship(foreign_keys=[equipment_id])
    probability: Mapped[Optional["Probability"]] = relationship(foreign_keys=[probability_id])
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    payment_items: Mapped[list["PaymentItem"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class Invoice(BaseID):
    __tablename__ = "invoices"
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    invoice_num: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_date: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    paid_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request: Mapped["Request"] = relationship(back_populates="invoices")


PAYMENT_TYPES = ["предоплата", "доплата-1", "доплата-2", "доплата-3", "отсрочка"]


class PaymentItem(BaseID):
    __tablename__ = "payment_items"
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    paid_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request: Mapped["Request"] = relationship(back_populates="payment_items")


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MaterialType(BaseID):
    __tablename__ = "material_types"
    name: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:
        return f"MaterialType(id={self.id}, name='{self.name}')"


class Material(BaseID):
    __tablename__ = "materials"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    code_1c: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code_agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type_id: Mapped[int | None] = mapped_column(ForeignKey("material_types.id", ondelete="SET NULL"), nullable=True)

    type: Mapped[Optional["MaterialType"]] = relationship(foreign_keys=[type_id])

    def __repr__(self) -> str:
        return f"Material(id={self.id}, name='{self.name}', price={self.price})"


class Module(BaseID):
    __tablename__ = "modules"
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    items: Mapped[list["ModuleItem"]] = relationship(
        back_populates="module", cascade="all, delete-orphan", foreign_keys="ModuleItem.module_id"
    )

    @property
    def total_price(self) -> float:
        from sqlalchemy.orm import attributes

        if attributes.instance_state(self).dict.get("items") is None:
            return 0.0
        total = 0.0
        for item in self.items:
            if item.material:
                total += float(item.material.price) * item.quantity
            elif item.sub_module:
                total += item.sub_module.total_price * item.quantity
        return total

    @property
    def items_count(self) -> int:
        from sqlalchemy.orm import attributes

        if attributes.instance_state(self).dict.get("items") is None:
            return 0
        return len(self.items)

    def __repr__(self) -> str:
        return f"Module(id={self.id}, name='{self.name}')"


class ModuleItem(Base):
    __tablename__ = "module_items"
    __table_args__ = (
        CheckConstraint(
            "(material_id IS NOT NULL AND sub_module_id IS NULL) OR "
            "(material_id IS NULL AND sub_module_id IS NOT NULL)",
            name="ck_module_item_one_ref",
        ),
        UniqueConstraint("module_id", "material_id", "sub_module_id", name="uq_module_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), nullable=False)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)
    sub_module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    module: Mapped["Module"] = relationship(foreign_keys=[module_id], back_populates="items")
    material: Mapped[Optional["Material"]] = relationship(foreign_keys=[material_id])
    sub_module: Mapped[Optional["Module"]] = relationship(foreign_keys=[sub_module_id])
