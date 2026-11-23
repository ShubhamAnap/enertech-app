from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, Identity, get_current_identity, require_admin_roles
from app.db.session import get_session
from app.models import AuditEvent, CustomerRequest
from app.schemas.cms import CustomerRequestAdmin, CustomerRequestPublic, CustomerRequestUpdate, QuoteRequestWrite, ServiceRequestWrite

router = APIRouter(tags=["customer requests"])
ADMIN_ROLES = ("content_editor", "admin", "super_admin")
REQUEST_ROLES = ("admin", "super_admin")
STATUS_BY_KIND = {
    "service": {"in_review", "assigned", "waiting_for_customer", "resolved", "closed"},
    "quote": {"in_review", "assigned", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"},
}


def _require_verified_customer(identity: Identity) -> None:
    if not identity.email or not identity.claims.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Verify your email address before submitting a request")


def _public(record: CustomerRequest) -> CustomerRequestPublic:
    return CustomerRequestPublic(
        id=record.id, kind=record.kind, status=record.status, payload=record.payload,
        resolution_note=record.resolution_note, created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _to_admin(record: CustomerRequest) -> CustomerRequestAdmin:
    return CustomerRequestAdmin(
        **_public(record).model_dump(), customer_uid=record.customer_uid,
        customer_email=record.customer_email, assigned_to=record.assigned_to,
    )


def _create(kind: str, payload: dict[str, object], identity: Identity, session: Session) -> CustomerRequestPublic:
    _require_verified_customer(identity)
    now = datetime.now(timezone.utc)
    record = CustomerRequest(
        id=uuid4(), customer_uid=identity.uid, customer_email=identity.email or "",
        kind=kind, status="submitted", payload=payload, created_at=now, updated_at=now,
    )
    session.add(record)
    session.add(AuditEvent(
        actor_uid=identity.uid, action=f"customer_request.{kind}.submitted",
        entity_type="customer_request", entity_id=str(record.id),
        change_summary={"kind": kind},
    ))
    session.commit()
    session.refresh(record)
    return _public(record)


@router.post("/requests/service", status_code=status.HTTP_201_CREATED, response_model=CustomerRequestPublic)
def submit_service_request(
    body: ServiceRequestWrite,
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CustomerRequestPublic:
    return _create("service", body.model_dump(mode="json"), identity, session)


@router.post("/requests/quote", status_code=status.HTTP_201_CREATED, response_model=CustomerRequestPublic)
def submit_quote_request(
    body: QuoteRequestWrite,
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CustomerRequestPublic:
    return _create("quote", body.model_dump(mode="json"), identity, session)


@router.get("/requests", response_model=list[CustomerRequestPublic])
def my_requests(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> list[CustomerRequestPublic]:
    rows = session.scalars(
        select(CustomerRequest).where(CustomerRequest.customer_uid == identity.uid)
        .order_by(CustomerRequest.created_at.desc()).limit(limit).offset(offset)
    )
    return [_public(record) for record in rows]


@router.get("/admin/requests", response_model=list[CustomerRequestAdmin])
def admin_requests(
    kind: str | None = Query(default=None, pattern="^(service|quote)$"),
    state: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    admin_identity: AdminIdentity = Depends(require_admin_roles(*REQUEST_ROLES)),
) -> list[CustomerRequestAdmin]:
    query = select(CustomerRequest)
    if kind:
        query = query.where(CustomerRequest.kind == kind)
    if state:
        query = query.where(CustomerRequest.status == state)
    _ = admin_identity
    return [_to_admin(record) for record in session.scalars(query.order_by(CustomerRequest.created_at.desc()).limit(limit).offset(offset))]


@router.patch("/admin/requests/{request_id}", response_model=CustomerRequestAdmin)
def update_request(
    request_id: UUID,
    body: CustomerRequestUpdate,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*REQUEST_ROLES)),
) -> CustomerRequestAdmin:
    record = session.get(CustomerRequest, request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if body.status not in STATUS_BY_KIND[record.kind]:
        raise HTTPException(status_code=422, detail="This status is not available for the selected request type")
    previous = record.status
    record.status = body.status
    record.assigned_to = body.assigned_to
    record.resolution_note = body.resolution_note
    record.updated_at = datetime.now(timezone.utc)
    session.add(AuditEvent(
        actor_uid=admin.uid, action="customer_request.updated", entity_type="customer_request",
        entity_id=str(record.id), change_summary={"previous_status": previous, "status": body.status, "assigned": body.assigned_to is not None},
    ))
    session.commit()
    session.refresh(record)
    return _to_admin(record)
