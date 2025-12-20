# models.py
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey
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


class Base(DeclarativeBase):
    pass


class BaseID(Base):
    """Абстрактный базовый класс с полями id, created_at и updated_at."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
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


class Manager(BaseID):
    """Модель менеджера."""

    __tablename__ = "managers"
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    organizations: Mapped[List["Organization"]] = relationship(back_populates="manager")

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
    """Модель организации."""

    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inn: Mapped[str] = mapped_column(String(12), unique=True, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    director_id: Mapped[int] = mapped_column(ForeignKey("directors.id"), nullable=False)
    manager_id: Mapped[int] = mapped_column(ForeignKey("managers.id"), nullable=False)

    director: Mapped["Directors"] = relationship(back_populates="organizations")
    manager: Mapped["Manager"] = relationship(back_populates="organizations")

    def __repr__(self) -> str:
        director_name = self.director.name if self.director else "None"
        manager_name = self.manager.name if self.manager else "None"
        return (
            f"Organization(id={self.id}, "
            f"name='{self.name}', "
            f"inn='{self.inn}', "
            f"director='{director_name}', "
            f"address='{self.address}', "
            f"manager='{manager_name}')"
        )


class Directors(BaseID):
    """Модель директора."""

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
    """Модель должности."""

    __tablename__ = "positions"
    title: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    directors: Mapped[List["Directors"]] = relationship(back_populates="position")

    def __repr__(self) -> str:
        return f"Positions(id={self.id}, " f"title='{self.title}')"
