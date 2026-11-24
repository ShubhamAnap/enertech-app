from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AdminIdentity, require_admin_roles
from app.db.session import get_session
from app.models import AdminAccount, AuditEvent
from app.schemas.cms import AdminAccountPublic, AdminAccountWrite, AuditEventPublic

router = APIRouter(tags=["admin operations"])


def _account_public(account: AdminAccount) -> AdminAccountPublic:
    return AdminAccountPublic(
        id=account.id,
        firebase_uid=account.firebase_uid,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        is_active=account.is_active,
        created_at=account.created_at.isoformat(),
        updated_at=account.updated_at.isoformat(),
    )


@router.get("/admin/accounts", response_model=list[AdminAccountPublic])
def list_admin_accounts(
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles("super_admin")),
) -> list[AdminAccountPublic]:
    accounts = session.scalars(select(AdminAccount).order_by(AdminAccount.created_at, AdminAccount.email))
    return [_account_public(account) for account in accounts]


@router.get("/admin/assignable-staff", response_model=list[AdminAccountPublic])
def list_assignable_staff(
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles("admin", "super_admin")),
) -> list[AdminAccountPublic]:
    accounts = session.scalars(
        select(AdminAccount)
        .where(AdminAccount.is_active.is_(True), AdminAccount.role.in_(["admin", "super_admin"]))
        .order_by(AdminAccount.display_name, AdminAccount.email)
    )
    return [_account_public(account) for account in accounts]


@router.put("/admin/accounts/{firebase_uid}", response_model=AdminAccountPublic)
def upsert_admin_account(
    firebase_uid: str,
    body: AdminAccountWrite,
    session: Session = Depends(get_session),
    admin: AdminIdentity = Depends(require_admin_roles("super_admin")),
) -> AdminAccountPublic:
    uid = firebase_uid.strip()
    if body.firebase_uid != uid:
        raise HTTPException(status_code=422, detail="The account UID in the path and form must match")
    if uid == admin.uid and (body.role != "super_admin" or not body.is_active):
        raise HTTPException(status_code=409, detail="You cannot remove your own active super-admin access")
    account = session.scalar(select(AdminAccount).where(AdminAccount.firebase_uid == uid))
    creating = account is None
    if account is None:
        account = AdminAccount(firebase_uid=uid)
        session.add(account)
    previous = {"role": account.role, "is_active": account.is_active} if not creating else None
    account.email = body.email.strip().lower() if body.email else None
    account.display_name = body.display_name.strip() if body.display_name else None
    account.role = body.role
    account.is_active = body.is_active
    session.add(AuditEvent(
        actor_uid=admin.uid,
        action="admin_account.created" if creating else "admin_account.updated",
        entity_type="admin_account",
        entity_id=uid,
        change_summary={"previous": previous, "role": body.role, "is_active": body.is_active},
    ))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This Firebase UID already has a CMS account") from error
    session.refresh(account)
    return _account_public(account)


@router.get("/admin/audit-events", response_model=list[AuditEventPublic])
def list_audit_events(
    entity_type: str | None = Query(default=None, max_length=80),
    action: str | None = Query(default=None, max_length=100),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    _admin: AdminIdentity = Depends(require_admin_roles("super_admin", "admin")),
) -> list[AuditEventPublic]:
    statement = select(AuditEvent)
    if entity_type and entity_type.strip():
        statement = statement.where(AuditEvent.entity_type == entity_type.strip())
    if action and action.strip():
        statement = statement.where(AuditEvent.action == action.strip())
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(
            AuditEvent.actor_uid.ilike(term),
            AuditEvent.action.ilike(term),
            AuditEvent.entity_type.ilike(term),
            AuditEvent.entity_id.ilike(term),
            cast(AuditEvent.change_summary, String).ilike(term),
        ))
    events = session.scalars(statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit).offset(offset))
    return [
        AuditEventPublic(
            id=event.id,
            actor_uid=event.actor_uid,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            change_summary=event.change_summary or {},
            created_at=event.created_at.isoformat(),
        )
        for event in events
    ]
