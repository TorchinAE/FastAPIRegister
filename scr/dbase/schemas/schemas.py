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


# --- Organization (Company) ---

class OrganizationAddSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: str = "/02_сторонние_заказчики"
    director_id: int
    rentability: Optional[float] = None


class OrganizationUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: Optional[str] = None
    director_id: Optional[int] = None
    rentability: Optional[float] = None


class OrganizationResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    inn: Optional[str] = None
    address: Optional[str] = None
    server_address_slug: str
    director_id: int
    rentability: Optional[float] = None
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


# --- Equipment ---

class EquipmentCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class EquipmentUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None


class EquipmentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: Optional[str] = None


# --- EquipmentSection ---

class EquipmentSectionCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class EquipmentSectionUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None


class EquipmentSectionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: Optional[str] = None


# --- Request ---

class RequestCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    counterparty_id: Optional[int] = None
    company_id: Optional[int] = None
    equipment_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: RequestStatus = RequestStatus.ZAPROS
    cost: float = Field(0, ge=0)
    issue_date: Optional[datetime] = None
    incoming_letter_num: Optional[str] = None
    repeat_tkp: Optional[str] = None
    invoice_num: Optional[str] = None
    invoice_date: Optional[datetime] = None
    factory_order_num: Optional[str] = None
    factory_order_date: Optional[datetime] = None
    ship_date: Optional[datetime] = None
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
    company_id: Optional[int] = None
    manager_id: Optional[int] = None
    equipment_id: Optional[int] = None
    probability_id: Optional[int] = None
    project_stamp: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[RequestStatus] = None
    request_date: Optional[datetime] = None
    issue_date: Optional[datetime] = None
    incoming_letter_num: Optional[str] = None
    repeat_tkp: Optional[str] = None
    invoice_num: Optional[str] = None
    invoice_date: Optional[datetime] = None
    factory_order_num: Optional[str] = None
    factory_order_date: Optional[datetime] = None
    ship_date: Optional[datetime] = None
    cost: Optional[float] = Field(None, ge=0)
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
    equipment_id: Optional[int] = None
    probability_id: Optional[int] = None
    project_stamp: Optional[str] = None
    request_date: datetime
    issue_date: Optional[datetime] = None
    status: RequestStatus
    cost: float = 0
    description: Optional[str] = None
    notes: Optional[str] = None
    tkp_num: Optional[str] = None
    incoming_letter_num: Optional[str] = None
    repeat_tkp: Optional[str] = None
    invoice_num: Optional[str] = None
    invoice_date: Optional[datetime] = None
    factory_order_num: Optional[str] = None
    factory_order_date: Optional[datetime] = None
    ship_date: Optional[datetime] = None
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


# --- Invoice ---

class InvoiceCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    invoice_num: Optional[str] = None
    invoice_date: Optional[datetime] = None
    percent: float = Field(0, ge=0, le=100)
    amount: float = Field(0, ge=0)
    paid_amount: float = Field(0, ge=0)
    paid_date: Optional[datetime] = None


class InvoiceUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_num: Optional[str] = None
    invoice_date: Optional[datetime] = None
    percent: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)
    paid_amount: Optional[float] = Field(None, ge=0)
    paid_date: Optional[datetime] = None


class InvoiceResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    invoice_num: Optional[str] = None
    invoice_date: datetime
    percent: float = 0
    amount: float = 0
    paid_amount: float = 0
    paid_date: Optional[datetime] = None
    created_by: Optional[str] = None


# --- PaymentItem ---

class PaymentItemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    payment_type: str
    amount: float = Field(0, ge=0)
    percent: float = Field(0, ge=0, le=100)
    due_date: Optional[datetime] = None
    paid_amount: float = Field(0, ge=0)
    paid_date: Optional[datetime] = None


class PaymentItemUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Optional[float] = Field(None, ge=0)
    percent: Optional[float] = Field(None, ge=0, le=100)
    due_date: Optional[datetime] = None
    paid_amount: Optional[float] = Field(None, ge=0)
    paid_date: Optional[datetime] = None


class PaymentItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    payment_type: str
    amount: float = 0
    percent: float = 0
    due_date: Optional[datetime] = None
    paid_amount: float = 0
    paid_date: Optional[datetime] = None
    created_by: Optional[str] = None


# --- Pagination ---

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
