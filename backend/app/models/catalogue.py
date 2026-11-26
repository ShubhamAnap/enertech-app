from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


product_category_links = Table(
    "product_category_links",
    Base.metadata,
    Column("product_id", Uuid, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Uuid, ForeignKey("product_categories.id", ondelete="CASCADE"), primary_key=True),
)


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wordpress_source_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    cms_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    products: Mapped[list["Product"]] = relationship(back_populates="category", foreign_keys="Product.category_id")
    categorized_products: Mapped[list["Product"]] = relationship(secondary=product_category_links, back_populates="categories")
    catalogue_mapping: Mapped["ProductCategoryCatalogue | None"] = relationship(
        back_populates="category",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ProductCategoryCatalogue(Base):
    """Stores category/product-family level PDF brochures for catalogue inheritance."""

    __tablename__ = "product_category_catalogues"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    category_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("product_categories.id", ondelete="CASCADE"), nullable=True, index=True)
    wordpress_category_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(180), default="Category catalogue PDF")
    catalog_pdf_url: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="cms")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category: Mapped[ProductCategory | None] = relationship(back_populates="catalogue_mapping")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("product_categories.id", ondelete="RESTRICT"), index=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    name: Mapped[str] = mapped_column(String(220))
    model_code: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    applications: Mapped[list[str]] = mapped_column(JSON, default=list)
    features: Mapped[list[str]] = mapped_column(JSON, default=list)
    specifications: Mapped[dict] = mapped_column(JSON, default=dict)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gallery_images: Mapped[list[str]] = mapped_column(JSON, default=list)
    price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR")
    currency_minor_unit: Mapped[int] = mapped_column(Integer, default=2)
    stock_status: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    documents: Mapped[list[dict]] = mapped_column(JSON, default=list)
    wordpress_source_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True)
    wordpress_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_override: Mapped[bool] = mapped_column(Boolean, default=False)
    documents_override: Mapped[bool] = mapped_column(Boolean, default=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    draft_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category: Mapped[ProductCategory] = relationship(back_populates="products", foreign_keys=[category_id])
    categories: Mapped[list[ProductCategory]] = relationship(secondary=product_category_links, back_populates="categorized_products")

    @property
    def category_ids(self) -> list[UUID]:
        return [category.id for category in self.categories] or [self.category_id]
