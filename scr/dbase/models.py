from datetime import datetime, timezone
from typing import Optional, Union, List

from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy."""
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
    changed_by_id: Mapped[Union[int, None]] = mapped_column(nullable=True, default=None)


class Manager(BaseID):
    """Модель менеджера."""
    __tablename__ = "managers"
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    organizations: Mapped[List["Organization"]] = relationship(
        back_populates="manager")

    def __repr__(self) -> str:
        return (f"Manager(id={self.id}, "
                f"name='{self.name}', "
                f"short_name='{self.short_name}', "
                f"phone='{self.phone}', "
                f"email='{self.email}')")


class Organization(BaseID):
    """Модель организации."""
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inn: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    director_id: Mapped[int] = mapped_column(ForeignKey('directors.id'), nullable=False)
    manager_id: Mapped[int] = mapped_column(ForeignKey('managers.id'), nullable=False)

    director: Mapped["Directors"] = relationship(back_populates="organizations")
    manager: Mapped["Manager"] = relationship(back_populates="organizations")

    def __repr__(self) -> str:
        director_name = self.director.name if self.director else "None"
        manager_name = self.manager.name if self.manager else "None"
        return (f"Organization(id={self.id}, "
                f"name='{self.name}', "
                f"inn='{self.inn}', "
                f"director='{director_name}', "
                f"address='{self.address}', "
                f"manager='{manager_name}')")


class Directors(BaseID):
    """Модель директора."""
    __tablename__ = "directors"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    petition_id: Mapped[int] = mapped_column(ForeignKey("petitions.id"), nullable=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)

    petition: Mapped["Petitions"] = relationship(back_populates="directors")
    post: Mapped["Posts"] = relationship(back_populates="directors")

    organizations: Mapped[List["Organization"]] = relationship(back_populates="director")


def __repr__(self) -> str:
        post_name = self.post.name if self.post else "None"
        org_names = [org.name for org in self.organizations] if self.organizations else []
        return (f"Director(id={self.id}, "
                f"name='{self.name}', "
                f"short_name='{self.short_name}', "
                f"post='{post_name}', "
                f"email='{self.email}', "
                f"phone='{self.phone}', "
                f"organizations={org_names})")


class Petitions(BaseID):
    """Модель обращения."""
    __tablename__ = "petitions"
    petition: Mapped[str] = mapped_column(String(200), nullable=False)
    directors: Mapped[List["Directors"]] = relationship(
        back_populates="petition")

    def __repr__(self) -> str:
        return f"Petition(id={self.id}, petition='{self.petition}')"


class Posts(BaseID):
    """Модель должности."""
    __tablename__ = "posts"
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    directors: Mapped[List["Directors"]] = relationship(back_populates="post")

    def __repr__(self) -> str:
        return (f"Post(id={self.id}, "
                f"name='{self.name}')")