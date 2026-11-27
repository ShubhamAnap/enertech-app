from datetime import datetime, timezone
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, Identity, delete_firebase_user, get_current_identity, require_admin_roles
from app.db.session import get_session
from app.api.app_content import _published_legal
from app.models import AdminAccount, AuditEvent, ContactInquiry, CustomerProfile, CustomerRequest, LegalAcceptance
from app.schemas.cms import CustomerProfilePublic, CustomerProfileWithConsentWrite, CustomerProfileWrite

router = APIRouter(tags=["customer profiles"])


def _public(profile: CustomerProfile) -> CustomerProfilePublic:
    return CustomerProfilePublic(
        id=profile.id, customer_type=profile.customer_type, name=profile.name,
        mobile_number=profile.mobile_number, email=profile.email, location=profile.location,
        company_name=profile.company_name, gst_number=profile.gst_number,
        created_at=profile.created_at.isoformat(), updated_at=profile.updated_at.isoformat(),
    )


def _verified_email(identity: Identity) -> str:
    if not identity.email or not identity.claims.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Verify your sign-in email before completing your customer profile")
    return identity.email.strip().lower()


@router.get("/customers/me", response_model=CustomerProfilePublic | None)
def get_my_profile(
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CustomerProfilePublic | None:
    _verified_email(identity)
    profile = session.scalar(select(CustomerProfile).where(CustomerProfile.firebase_uid == identity.uid))
    return _public(profile) if profile is not None else None


@router.put("/customers/me", response_model=CustomerProfilePublic)
def save_my_profile(
    body: CustomerProfileWrite,
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CustomerProfilePublic:
    return _save_profile(body.model_dump(mode="json"), identity, session)


@router.put("/customers/me/with-consent", response_model=CustomerProfilePublic)
def save_my_profile_with_consent(
    body: CustomerProfileWithConsentWrite,
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> CustomerProfilePublic:
    privacy = _published_legal("privacy_policy", session)
    terms = _published_legal("terms", session)
    if body.privacy_version_id != privacy.id or body.terms_version_id != terms.id:
        raise HTTPException(status_code=409, detail="The legal pages changed. Review the current versions and accept again.")
    values = body.model_dump(mode="json", exclude={"privacy_version_id", "terms_version_id", "accepted"})
    return _save_profile(values, identity, session, (privacy.id, terms.id))


def _save_profile(
    values: dict[str, object],
    identity: Identity,
    session: Session,
    consent_versions: tuple[UUID, UUID] | None = None,
) -> CustomerProfilePublic:
    auth_email = _verified_email(identity)
    if str(values["email"]).lower() != auth_email:
        raise HTTPException(status_code=422, detail="Use the verified email address for your signed-in account")
    business = values["customer_type"] != "end_user"
    if business and (not values["company_name"] or not values["gst_number"]):
        raise HTTPException(status_code=422, detail="Company name and GST number are required for business accounts")
    profile = session.scalar(select(CustomerProfile).where(CustomerProfile.firebase_uid == identity.uid))
    changed = [key for key in values if profile is None or getattr(profile, key) != values[key]]
    if profile is None:
        profile = CustomerProfile(firebase_uid=identity.uid, **values)
        session.add(profile)
        action = "customer_profile.created"
    else:
        for key, value in values.items():
            setattr(profile, key, value)
        profile.updated_at = datetime.now(timezone.utc)
        action = "customer_profile.updated"
    session.add(AuditEvent(actor_uid=identity.uid, action=action, entity_type="customer_profile", entity_id=identity.uid, change_summary={"changed_fields": changed}))
    if consent_versions is not None:
        privacy_id, terms_id = consent_versions
        existing = session.scalar(select(LegalAcceptance).where(
            LegalAcceptance.customer_uid == identity.uid,
            LegalAcceptance.privacy_version_id == privacy_id,
            LegalAcceptance.terms_version_id == terms_id,
        ))
        if existing is None:
            session.add(LegalAcceptance(
                customer_uid=identity.uid,
                privacy_version_id=privacy_id,
                terms_version_id=terms_id,
                accepted_at=datetime.now(timezone.utc),
            ))
            session.add(AuditEvent(
                actor_uid=identity.uid, action="customer_legal.accepted",
                entity_type="customer_profile", entity_id=identity.uid,
                change_summary={"privacy_version_id": str(privacy_id), "terms_version_id": str(terms_id)},
            ))
    session.commit()
    session.refresh(profile)
    return _public(profile)


@router.delete("/customers/me", response_model=dict[str, object])
def delete_my_account(
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    _verified_email(identity)
    active_admin = session.scalar(
        select(AdminAccount).where(AdminAccount.firebase_uid == identity.uid, AdminAccount.is_active.is_(True))
    )
    if active_admin is not None:
        raise HTTPException(
            status_code=409,
            detail="Active CMS administrator accounts cannot be deleted from the customer app",
        )

    anonymized_uid = f"deleted-{hashlib.sha256(identity.uid.encode('utf-8')).hexdigest()[:24]}"
    anonymized_email = f"{anonymized_uid}@deleted.invalid"

    profiles = list(session.scalars(select(CustomerProfile).where(CustomerProfile.firebase_uid == identity.uid)))
    for profile in profiles:
        session.delete(profile)

    requests = list(session.scalars(select(CustomerRequest).where(CustomerRequest.customer_uid == identity.uid)))
    for req in requests:
        req.customer_uid = anonymized_uid
        req.customer_email = anonymized_email
        payload = dict(req.payload) if isinstance(req.payload, dict) else {}
        if "customer_name" in payload:
            payload["customer_name"] = "Deleted Customer"
        if "email" in payload:
            payload["email"] = anonymized_email
        if "mobile_number" in payload:
            payload["mobile_number"] = "Removed"
        req.payload = payload

    inquiries = list(session.scalars(select(ContactInquiry).where(ContactInquiry.customer_uid == identity.uid)))
    for inquiry in inquiries:
        inquiry.customer_uid = None
        inquiry.name = "Deleted Customer"
        inquiry.email = anonymized_email
        inquiry.phone = "Removed"
        inquiry.company_name = None

    acceptances = list(session.scalars(select(LegalAcceptance).where(LegalAcceptance.customer_uid == identity.uid)))
    for acceptance in acceptances:
        duplicate = session.scalar(
            select(LegalAcceptance).where(
                LegalAcceptance.customer_uid == anonymized_uid,
                LegalAcceptance.privacy_version_id == acceptance.privacy_version_id,
                LegalAcceptance.terms_version_id == acceptance.terms_version_id,
            )
        )
        if duplicate is not None:
            session.delete(acceptance)
        else:
            acceptance.customer_uid = anonymized_uid

    session.add(
        AuditEvent(
            actor_uid=anonymized_uid,
            action="customer_account.deleted",
            entity_type="customer_profile",
            entity_id=anonymized_uid,
            change_summary={
                "profiles_deleted": len(profiles),
                "requests_anonymized": len(requests),
                "inquiries_anonymized": len(inquiries),
                "legal_acceptances_anonymized": len(acceptances),
            },
        )
    )
    session.flush()
    try:
        delete_firebase_user(identity.uid)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "status": "deleted",
        "preserved_requests": len(requests),
        "preserved_inquiries": len(inquiries),
    }


@router.get("/admin/customers", response_model=list[CustomerProfilePublic])
def list_customers(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles("admin", "super_admin")),
) -> list[CustomerProfilePublic]:
    statement = select(CustomerProfile)
    if q and q.strip():
        value = f"%{q.strip()}%"
        statement = statement.where(
            CustomerProfile.name.ilike(value) | CustomerProfile.email.ilike(value)
            | CustomerProfile.mobile_number.ilike(value) | CustomerProfile.company_name.ilike(value)
        )
    rows = session.scalars(statement.order_by(CustomerProfile.updated_at.desc()).limit(limit).offset(offset))
    return [_public(profile) for profile in rows]
