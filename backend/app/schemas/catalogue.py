from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductDocument(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    url: str = Field(min_length=8, max_length=1000, pattern=r"^https://")


class CategoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    description: str | None
    image_url: str | None


class ProductPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    model_code: str | None
    summary: str | None
    description: str | None
    applications: list[str]
    features: list[str]
    specifications: dict[str, object]
    image_url: str | None
    gallery_images: list[str]
    price_minor: int | None
    currency_code: str
    currency_minor_unit: int
    stock_status: str
    stock_quantity: int | None
    documents: list[ProductDocument]
    category_id: UUID
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductPublic]
    total: int = Field(ge=0)
    # Both the public catalogue and CMS use bounded pages up to 500 rows.
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
