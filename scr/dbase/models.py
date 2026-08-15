# models.py
import enum
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, Enum, Table, Column, Numeric
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
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    changed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("managers.id"), nullable=True
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    city: Mapped[str] = mapped_column(String(50), nullable=False, default="ив")
    signature: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    managers: Mapped[List["Manager"]] = relationship(back_populates="user")


organization_managers = Table(
    "organization_managers",
    Base.metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id"), primary_key=True),
    Column("manager_id", Integer, ForeignKey("managers.id"), primary_key=True),
)


class Manager(BaseID):
    __tablename__ = "managers"
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    organizations: Mapped[List["Organization"]] = relationship(
        back_populates="managers", secondary=organization_managers
    )
    user: Mapped[Optional["User"]] = relationship(back_populates="managers", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return (
            f"Manager(id={self.id}, "
            f"name='{self.name}', "
            f"phone='{self.phone}', "
            f"email='{self.email}')"
        )

    @property
    def short_name(self) -> str:
        return get_short_name(self.name)


class Organization(BaseID):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inn: Mapped[str] = mapped_column(String(12), unique=True, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    server_address_slug: Mapped[str] = mapped_column(
        String(200), nullable=False, default="/02_сторонние_заказчики"
    )
    director_id: Mapped[int] = mapped_column(ForeignKey("directors.id"), nullable=False)

    director: Mapped["Directors"] = relationship(back_populates="organizations")
    managers: Mapped[List["Manager"]] = relationship(
        back_populates="organizations", secondary=organization_managers
    )
    counterparties: Mapped[List["Counterparty"]] = relationship(
        back_populates="company"
    )

    def __repr__(self) -> str:
        director_name = self.director.name if self.director else "None"
        manager_names = [m.name for m in self.managers] if self.managers else []
        return (
            f"Organization(id={self.id}, "
            f"name='{self.name}', "
            f"inn='{self.inn}', "
            f"director='{director_name}', "
            f"address='{self.address}', "
            f"managers={manager_names})"
        )


class Directors(BaseID):
    __tablename__ = "directors"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))

    position: Mapped["Positions"] = relationship(back_populates="directors")
    organizations: Mapped[List["Organization"]] = relationship(
        back_populates="director"
    )

    @property
    def short_name(self) -> str:
        return get_short_name(self.name)

    @property
    def give_name(self) -> str:
        return get_give_name(self.name)

    def __repr__(self) -> str:
        org_names = (
            [org.name for org in self.organizations] if self.organizations else []
        )
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
    directors: Mapped[List["Directors"]] = relationship(back_populates="position")

    def __repr__(self) -> str:
        return f"Positions(id={self.id}, name='{self.name}')"


class Counterparty(BaseID):
    __tablename__ = "counterparties"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )

    company: Mapped["Organization"] = relationship(back_populates="counterparties")


class Equipment(BaseID):
    __tablename__ = "equipment"
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"Equipment(id={self.id}, name='{self.name}')"


class Request(BaseID):
    __tablename__ = "requests"
    counterparty_id: Mapped[int] = mapped_column(
        ForeignKey("counterparties.id"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    manager_id: Mapped[int] = mapped_column(ForeignKey("managers.id"), nullable=False)
    equipment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("equipment.id"), nullable=True
    )
    request_date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    issue_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.ZAPROS, nullable=False
    )
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tkp_num: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

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
    manager: Mapped["Manager"] = relationship(foreign_keys=[manager_id])
    equipment: Mapped[Optional["Equipment"]] = relationship(foreign_keys=[equipment_id])
