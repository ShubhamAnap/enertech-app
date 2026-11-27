from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, Identity, get_current_identity, require_admin_roles
from app.db.session import get_session
from app.api.app_content import _published_legal
from app.models import AuditEvent, CustomerProfile, LegalAcceptance
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
