from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

from scr.dbase.models import RequestStatus


# --- Base ---

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    changed_by_id: Optional[int] = None


# --- Auth ---

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    city: str = "ив"
    signature: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    city: str = "ив"
    signature: Optional[str] = None


# --- Position ---

class PositionCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class PositionUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None


class PositionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: Optional[str] = None


# --- Manager ---

class ManagerCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    phone: str
    user_id: Optional[int] = None


class ManagerUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    user_id: Optional[int] = None


class ManagerResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
    email: str
    phone: str
    user_id: Optional[int] = None
    created_by: Optional[str] = None


# --- Organization (Company) ---

class OrganizationAddSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: str = "/02_сторонние_заказчики"
    director_id: int
    manager_ids: list[int] = []


class OrganizationUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: Optional[str] = None
    director_id: Optional[int] = None
    manager_ids: Optional[list[int]] = None


class ManagerShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class OrganizationResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: str
    director_id: int
    managers: list[ManagerShort] = []
    created_by: Optional[str] = None


# --- Director ---

class DirectorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position_id: int


class DirectorUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position_id: Optional[int] = None


class DirectorResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: PositionResponseSchema
    created_by: Optional[str] = None


class DirectorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    directors: list[DirectorResponseSchema]


# --- Counterparty ---

class CounterpartyCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    phone: Optional[str] = None
    company_id: int


class CounterpartyUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[int] = None


class CounterpartyResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    company_id: int
    company_name: Optional[str] = None
    created_by: Optional[str] = None


# --- Request ---

EQUIPMENT_FIELDS = [
    "bktpb", "ktpb", "ktp", "kso_393", "kso_204",
    "k_104", "k_104m", "sho", "pku", "pus", "parn",
]


class RequestCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    counterparty_id: int
    description: Optional[str] = None
    notes: Optional[str] = None
    status: RequestStatus = RequestStatus.ZAPROS
    bktpb: int = Field(0, ge=0, le=100)
    ktpb: int = Field(0, ge=0, le=100)
    ktp: int = Field(0, ge=0, le=100)
    kso_393: int = Field(0, ge=0, le=100)
    kso_204: int = Field(0, ge=0, le=100)
    k_104: int = Field(0, ge=0, le=100)
    k_104m: int = Field(0, ge=0, le=100)
    sho: int = Field(0, ge=0, le=100)
    pku: int = Field(0, ge=0, le=100)
    pus: int = Field(0, ge=0, le=100)
    parn: int = Field(0, ge=0, le=100)


class RequestUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    counterparty_id: Optional[int] = None
    manager_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[RequestStatus] = None
    request_date: Optional[datetime] = None
    bktpb: Optional[int] = Field(None, ge=0, le=100)
    ktpb: Optional[int] = Field(None, ge=0, le=100)
    ktp: Optional[int] = Field(None, ge=0, le=100)
    kso_393: Optional[int] = Field(None, ge=0, le=100)
    kso_204: Optional[int] = Field(None, ge=0, le=100)
    k_104: Optional[int] = Field(None, ge=0, le=100)
    k_104m: Optional[int] = Field(None, ge=0, le=100)
    sho: Optional[int] = Field(None, ge=0, le=100)
    pku: Optional[int] = Field(None, ge=0, le=100)
    pus: Optional[int] = Field(None, ge=0, le=100)
    parn: Optional[int] = Field(None, ge=0, le=100)


class RequestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    counterparty_id: int
    company_id: int
    manager_id: int
    request_date: datetime
    status: RequestStatus
    description: Optional[str] = None
    notes: Optional[str] = None
    tkp_num: Optional[str] = None
    bktpb: int = 0
    ktpb: int = 0
    ktp: int = 0
    kso_393: int = 0
    kso_204: int = 0
    k_104: int = 0
    k_104m: int = 0
    sho: int = 0
    pku: int = 0
    pus: int = 0
    parn: int = 0
    created_by: Optional[str] = None


# --- Pagination ---

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
