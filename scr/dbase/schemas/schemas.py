from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from scr.dbase.models import RequestStatus

# --- Base ---


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    changed_by_id: int | None = None


# --- Auth ---


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None
    city: str = "ив"
    signature: str | None = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    city: str = "ив"
    signature: str | None = None


# --- Position ---


class PositionCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class PositionUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None


class PositionResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: str | None = None


# --- Organization (Company) ---


class OrganizationAddSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    inn: str | None = None
    address: str | None = None
    server_address_slug: str = "/02_сторонние_заказчики"
    director_id: int


class OrganizationUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    inn: str | None = None
    address: str | None = None
    server_address_slug: str | None = None
    director_id: int | None = None


class OrganizationResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    inn: str | None = None
    address: str | None = None
    server_address_slug: str
    director_id: int
    created_by: str | None = None


# --- Director ---


class DirectorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str | None = None
    phone: str | None = None
    position_id: int


class DirectorUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    position_id: int | None = None


class DirectorResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
    email: str | None = None
    phone: str | None = None
    position: PositionResponseSchema
    created_by: str | None = None


class DirectorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    directors: list[DirectorResponseSchema]


# --- Counterparty ---


class CounterpartyCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: str
    phone: str | None = None
    company_id: int


class CounterpartyUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_id: int | None = None


class CounterpartyResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None = None
    company_id: int
    company_name: str | None = None
    created_by: str | None = None


# --- Material Type ---


class MaterialTypeCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class MaterialTypeUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None


class MaterialTypeResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: str | None = None


# --- Material ---


class MaterialCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    price: float = Field(0, ge=0)
    code_1c: str | None = None
    code_agent: str | None = None
    url_agent: str | None = None
    type_id: int | None = None
    nom_tok: int = Field(0, ge=0, le=7000)
    stats: bool = True
    vtych: bool = False
    vykat: bool = False
    ruchn: bool = True
    el_priv: bool = False


class MaterialUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None
    price: float | None = Field(None, ge=0)
    code_1c: str | None = None
    code_agent: str | None = None
    url_agent: str | None = None
    type_id: int | None = None
    nom_tok: int | None = Field(None, ge=0, le=7000)
    stats: bool | None = None
    vtych: bool | None = None
    vykat: bool | None = None
    ruchn: bool | None = None
    el_priv: bool | None = None


class MaterialResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float = 0
    code_1c: str | None = None
    code_agent: str | None = None
    url_agent: str | None = None
    type_id: int | None = None
    type_name: str | None = None
    nom_tok: int = 0
    stats: bool = True
    vtych: bool = False
    vykat: bool = False
    ruchn: bool = True
    el_priv: bool = False
    created_by: str | None = None


# --- Module Item ---


class ModuleItemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_id: int | None = None
    sub_module_id: int | None = None
    quantity: int = Field(1, ge=1)


class ModuleItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    material_id: int | None = None
    sub_module_id: int | None = None
    quantity: int = 1
    material: MaterialResponseSchema | None = None
    sub_module_name: str | None = None


# --- Module ---


class ModuleCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class ModuleUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None


class ModuleResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    items_count: int = 0
    total_price: float = 0
    created_by: str | None = None


class ModuleFullResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    items: list[ModuleItemResponseSchema] = []
    total_price: float = 0
    created_by: str | None = None


# --- Equipment ---


class EquipmentCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str


class EquipmentUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None = None


class EquipmentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: str | None = None


# --- Request ---


class RequestCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    counterparty_id: int | None = None
    company_id: int | None = None
    equipment_id: int | None = None
    description: str | None = None
    notes: str | None = None
    status: RequestStatus = RequestStatus.ZAPROS
    cost: float = Field(0, ge=0)
    issue_date: datetime | None = None
    incoming_letter_num: str | None = None
    repeat_tkp: str | None = None
    invoice_num: str | None = None
    invoice_date: datetime | None = None
    factory_order_num: str | None = None
    factory_order_date: datetime | None = None
    ship_date: datetime | None = None
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
    counterparty_id: int | None = None
    company_id: int | None = None
    manager_id: int | None = None
    equipment_id: int | None = None
    probability_id: int | None = None
    project_stamp: str | None = None
    description: str | None = None
    notes: str | None = None
    status: RequestStatus | None = None
    request_date: datetime | None = None
    issue_date: datetime | None = None
    incoming_letter_num: str | None = None
    repeat_tkp: str | None = None
    invoice_num: str | None = None
    invoice_date: datetime | None = None
    factory_order_num: str | None = None
    factory_order_date: datetime | None = None
    ship_date: datetime | None = None
    cost: float | None = Field(None, ge=0)
    bktpb: int | None = Field(None, ge=0, le=100)
    ktpb: int | None = Field(None, ge=0, le=100)
    ktp: int | None = Field(None, ge=0, le=100)
    kso_393: int | None = Field(None, ge=0, le=100)
    kso_204: int | None = Field(None, ge=0, le=100)
    k_104: int | None = Field(None, ge=0, le=100)
    k_104m: int | None = Field(None, ge=0, le=100)
    sho: int | None = Field(None, ge=0, le=100)
    pku: int | None = Field(None, ge=0, le=100)
    pus: int | None = Field(None, ge=0, le=100)
    parn: int | None = Field(None, ge=0, le=100)


class RequestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    counterparty_id: int
    company_id: int
    manager_id: int
    equipment_id: int | None = None
    probability_id: int | None = None
    project_stamp: str | None = None
    request_date: datetime
    issue_date: datetime | None = None
    status: RequestStatus
    cost: float = 0
    description: str | None = None
    notes: str | None = None
    tkp_num: str | None = None
    incoming_letter_num: str | None = None
    repeat_tkp: str | None = None
    invoice_num: str | None = None
    invoice_date: datetime | None = None
    factory_order_num: str | None = None
    factory_order_date: datetime | None = None
    ship_date: datetime | None = None
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
    created_by: str | None = None


# --- Invoice ---


class InvoiceCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    invoice_num: str | None = None
    invoice_date: datetime | None = None
    percent: float = Field(0, ge=0, le=100)
    amount: float = Field(0, ge=0)
    paid_amount: float = Field(0, ge=0)
    paid_date: datetime | None = None


class InvoiceUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_num: str | None = None
    invoice_date: datetime | None = None
    percent: float | None = Field(None, ge=0, le=100)
    amount: float | None = Field(None, ge=0)
    paid_amount: float | None = Field(None, ge=0)
    paid_date: datetime | None = None


class InvoiceResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    invoice_num: str | None = None
    invoice_date: datetime
    percent: float = 0
    amount: float = 0
    paid_amount: float = 0
    paid_date: datetime | None = None
    created_by: str | None = None


# --- PaymentItem ---


class PaymentItemCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: int
    payment_type: str
    amount: float = Field(0, ge=0)
    percent: float = Field(0, ge=0, le=100)
    due_date: datetime | None = None
    paid_amount: float = Field(0, ge=0)
    paid_date: datetime | None = None


class PaymentItemUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float | None = Field(None, ge=0)
    percent: float | None = Field(None, ge=0, le=100)
    due_date: datetime | None = None
    paid_amount: float | None = Field(None, ge=0)
    paid_date: datetime | None = None


class PaymentItemResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    payment_type: str
    amount: float = 0
    percent: float = 0
    due_date: datetime | None = None
    paid_amount: float = 0
    paid_date: datetime | None = None
    created_by: str | None = None


# --- Pagination ---


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
