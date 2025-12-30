from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from scr.dbase.models import (
    Directors,
    Organization,
    Manager,
    Positions,
)
