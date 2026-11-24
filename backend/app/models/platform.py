from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAccount(Base):
    __tablename__ = "admin_accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="content_editor", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppConfig(Base):
    __tablename__ = "app_config"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    draft_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    published_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    draft_revision: Mapped[int] = mapped_column(Integer, default=1)
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_uid: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(160), index=True)
    change_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomerRequest(Base):
    __tablename__ = "customer_requests"
    __table_args__ = (Index("ix_customer_requests_customer_created", "customer_uid", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    customer_uid: Mapped[str] = mapped_column(String(128), index=True)
    customer_email: Mapped[str] = mapped_column(String(254))
    kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(40), default="submitted", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    assigned_to: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    resolution_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(100), default="General", index=True)
    answer: Mapped[str] = mapped_column(String(12000))
    source_reference: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    draft_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    customer_type: Mapped[str] = mapped_column(String(24), index=True)
    name: Mapped[str] = mapped_column(String(180))
    mobile_number: Mapped[str] = mapped_column(String(24))
    email: Mapped[str] = mapped_column(String(254))
    location: Mapped[str] = mapped_column(String(500))
    company_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContactInquiry(Base):
    __tablename__ = "contact_inquiries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    customer_uid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(24))
    company_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(220), nullable=True)
    message: Mapped[str] = mapped_column(String(10000))
    inquiry_type: Mapped[str] = mapped_column(String(50), default="general", index=True)
    status: Mapped[str] = mapped_column(String(40), default="new", index=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
