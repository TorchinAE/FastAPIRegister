from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class BaseSchema(BaseModel):
    id: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    changed_by_id: Optional[int] = None

    class Config:
        from_attributes = True


class PostResponseSchema(BaseModel):
    name: str

    class Config:
        from_attributes = True


class ManagerSchema(BaseSchema):
    name: str
    short_name: str
    email: str
    phone: str


class OrganizationSchema(BaseSchema):
    name: str
    inn: Optional[str]
    address: Optional[str]
    director_id: int
    manager_id: int


class DirectorsSchema(BaseModel):
    name: str
    short_name: str
    email: Optional[str]
    phone: Optional[str]


class DirectorAddSchema(BaseModel):
    name: str
    short_name: str
    email: Optional[str]
    phone: Optional[str]
    post_id: int
    petition_id: int

    class Config:
        from_attributes = True


class DirectorPatch(BaseModel):
    short_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    post_id: Optional[int] = None
    petition_id: Optional[int] = None

    class Config:
        from_attributes = True


class DirectorResponseSchema(BaseModel):
    id: int
    name: str
    short_name: str
    email: str
    phone: str
    post: PostResponseSchema

    class Config:
        from_attributes = True


class DirectorListResponse(BaseModel):
    directors: list[DirectorResponseSchema]

    class Config:
        from_attributes = True


class PetitionSchema(BaseSchema):
    petition: str
    directors: Optional[list]
