from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, Identity, get_current_identity, require_admin_roles
from app.db.session import get_session
from app.models import AdminAccount, AuditEvent, CustomerRequest, ContactInquiry
from app.schemas.cms import CustomerRequestAdmin, CustomerRequestPublic, CustomerRequestUpdate, QuoteRequestWrite, ServiceRequestWrite, ContactInquiryCreate, ContactInquiryAdmin, ContactInquiryUpdate

router = APIRouter(tags=["customer requests"])
ADMIN_ROLES = ("content_editor", "admin", "super_admin")
REQUEST_ROLES = ("admin", "super_admin")
REQUEST_TRANSITIONS = {
    "service": {
        "submitted": {"in_review", "assigned", "waiting_for_customer", "closed"},
        "in_review": {"assigned", "waiting_for_customer", "resolved", "closed"},
        "assigned": {"in_review", "waiting_for_customer", "resolved", "closed"},
        "waiting_for_customer": {"in_review", "assigned", "resolved", "closed"},
        "resolved": {"closed"},
        "closed": set(),
    },
    "quote": {
        "submitted": {"in_review", "assigned", "waiting_for_customer", "quote_preparing", "closed"},
        "in_review": {"assigned", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"},
        "assigned": {"in_review", "waiting_for_customer", "quote_preparing", "quote_sent", "closed"},
        "waiting_for_customer": {"in_review", "assigned", "quote_preparing", "quote_sent", "closed"},
        "quote_preparing": {"waiting_for_customer", "quote_sent", "closed"},
        "quote_sent": {"waiting_for_customer", "closed"},
        "closed": set(),
    },
}
CONTACT_INQUIRY_STATUSES = {"new", "in_progress", "waiting_for_customer", "resolved", "closed"}


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
    status_filter: str | None = Query(default=None, alias="status", pattern="^(submitted|in_review|assigned|waiting_for_customer|resolved|quote_preparing|quote_sent|closed)$"),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    admin_identity: AdminIdentity = Depends(require_admin_roles(*REQUEST_ROLES)),
) -> list[CustomerRequestAdmin]:
    query = select(CustomerRequest)
    if kind:
        query = query.where(CustomerRequest.kind == kind)
    if status_filter:
        query = query.where(CustomerRequest.status == status_filter)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(
            CustomerRequest.customer_email.ilike(term),
            CustomerRequest.customer_uid.ilike(term),
            cast(CustomerRequest.id, String).ilike(term),
            cast(CustomerRequest.payload, String).ilike(term),
        ))
    _ = admin_identity
    return [_to_admin(record) for record in session.scalars(query.order_by(CustomerRequest.created_at.desc(), CustomerRequest.id.desc()).limit(limit).offset(offset))]


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
    if body.status != record.status and body.status not in REQUEST_TRANSITIONS[record.kind].get(record.status, set()):
        raise HTTPException(status_code=409, detail="This request cannot move from its current status to the selected status")
    next_assignee = body.assigned_to if "assigned_to" in body.model_fields_set else record.assigned_to
    next_note = body.resolution_note if "resolution_note" in body.model_fields_set else record.resolution_note
    if body.status == "assigned" and not next_assignee:
        raise HTTPException(status_code=422, detail="Assign this request to an active CMS administrator before using the assigned status")
    if next_assignee and (next_assignee != record.assigned_to or body.status == "assigned"):
        assignee = session.scalar(select(AdminAccount).where(
            AdminAccount.firebase_uid == next_assignee,
            AdminAccount.is_active.is_(True),
            AdminAccount.role.in_(["admin", "super_admin"]),
        ))
        if assignee is None:
            raise HTTPException(status_code=422, detail="Choose an active CMS administrator for assignment")
    previous = record.status
    previous_assignee = record.assigned_to
    record.status = body.status
    record.assigned_to = next_assignee
    record.resolution_note = next_note
    record.updated_at = datetime.now(timezone.utc)
    session.add(AuditEvent(
        actor_uid=admin.uid, action="customer_request.updated", entity_type="customer_request",
        entity_id=str(record.id), change_summary={
            "previous_status": previous,
            "status": body.status,
            "previous_assignee": previous_assignee,
            "assignee": next_assignee,
        },
    ))
    session.commit()
    session.refresh(record)
    return _to_admin(record)


@router.post("/requests/contact-inquiry", status_code=status.HTTP_201_CREATED, response_model=dict[str, object])
def submit_contact_inquiry(
    body: ContactInquiryCreate,
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _require_verified_customer(identity)
    now = datetime.now(timezone.utc)
    recent_count = session.scalar(select(func.count()).select_from(ContactInquiry).where(
        ContactInquiry.created_at >= now - timedelta(hours=1),
        (ContactInquiry.customer_uid == identity.uid)
        | (
            ContactInquiry.customer_uid.is_(None)
            & (func.lower(ContactInquiry.email) == (identity.email or "").lower())
        ),
    )) or 0
    if recent_count >= 5:
        raise HTTPException(status_code=429, detail="You have sent several enquiries recently. Please try again later.")
    inquiry = ContactInquiry(
        id=uuid4(),
        customer_uid=identity.uid,
        name=body.name,
        email=identity.email or "",
        phone=body.phone,
        company_name=body.company_name,
        subject=body.subject,
        message=body.message,
        inquiry_type=body.inquiry_type,
        status="new",
        created_at=now,
        updated_at=now,
    )
    session.add(inquiry)
    session.add(AuditEvent(
        actor_uid=identity.uid,
        action="contact_inquiry.submitted",
        entity_type="contact_inquiry",
        entity_id=str(inquiry.id),
        change_summary={"inquiry_type": inquiry.inquiry_type},
    ))
    session.commit()
    return {"id": str(inquiry.id), "status": "received", "message": "Thank you for reaching out. We will get back to you shortly."}


@router.get("/admin/contact-inquiries", response_model=list[ContactInquiryAdmin])
def admin_contact_inquiries(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(new|in_progress|waiting_for_customer|resolved|closed)$"),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    admin_identity: AdminIdentity = Depends(require_admin_roles(*REQUEST_ROLES)),
) -> list[ContactInquiryAdmin]:
    query = select(ContactInquiry)
    if status_filter:
        query = query.where(ContactInquiry.status == status_filter)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(
            ContactInquiry.name.ilike(term), ContactInquiry.email.ilike(term),
            ContactInquiry.phone.ilike(term), ContactInquiry.company_name.ilike(term),
            ContactInquiry.subject.ilike(term), ContactInquiry.message.ilike(term),
        ))
    _ = admin_identity
    records = session.scalars(query.order_by(ContactInquiry.created_at.desc()).limit(limit).offset(offset))
    return [
        ContactInquiryAdmin(
            id=r.id,
            name=r.name,
            email=r.email,
            phone=r.phone,
            company_name=r.company_name,
            subject=r.subject,
            message=r.message,
            inquiry_type=r.inquiry_type,
            status=r.status,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in records
    ]


@router.patch("/admin/contact-inquiries/{inquiry_id}", response_model=ContactInquiryAdmin)
def update_contact_inquiry(
    inquiry_id: UUID,
    body: ContactInquiryUpdate,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles(*REQUEST_ROLES)),
) -> ContactInquiryAdmin:
    record = session.get(ContactInquiry, inquiry_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    if body.status not in CONTACT_INQUIRY_STATUSES:
        raise HTTPException(status_code=422, detail="Choose a supported contact inquiry status")
    record.status = body.status
    if body.notes is not None:
        record.notes = body.notes
    record.updated_at = datetime.now(timezone.utc)
    session.add(AuditEvent(
        actor_uid=admin.uid, action="contact_inquiry.updated", entity_type="contact_inquiry",
        entity_id=str(record.id), change_summary={"status": body.status, "notes_updated": body.notes is not None},
    ))
    session.commit()
    session.refresh(record)
    return ContactInquiryAdmin(
        id=record.id,
        name=record.name,
        email=record.email,
        phone=record.phone,
        company_name=record.company_name,
        subject=record.subject,
        message=record.message,
        inquiry_type=record.inquiry_type,
        status=record.status,
        notes=record.notes,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )

