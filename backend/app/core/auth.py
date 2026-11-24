import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth, credentials
from firebase_admin.exceptions import FirebaseError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.models.platform import AdminAccount

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str | None
    name: str | None
    claims: dict[str, Any]


@dataclass(frozen=True)
class AdminIdentity:
    uid: str
    email: str | None
    name: str | None
    role: str


@lru_cache
def _firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if not settings.firebase_project_id:
        raise HTTPException(status_code=503, detail="Firebase Authentication is not configured")

    if settings.firebase_auth_emulator_host:
        os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = settings.firebase_auth_emulator_host

    options = {"projectId": settings.firebase_project_id}
    if settings.firebase_service_account_json:
        try:
            service_account = json.loads(settings.firebase_service_account_json)
            credential = credentials.Certificate(service_account)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(status_code=503, detail="Firebase server credentials are invalid") from error
    elif settings.firebase_auth_emulator_host:
        credential = None
    else:
        raise HTTPException(status_code=503, detail="Firebase server credentials are not configured")

    try:
        return firebase_admin.initialize_app(credential, options=options)
    except ValueError:
        return firebase_admin.get_app()


def get_current_identity(
    credentials_header: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Identity:
    if credentials_header is None or credentials_header.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign-in is required")
    try:
        claims = firebase_auth.verify_id_token(credentials_header.credentials, app=_firebase_app(), check_revoked=True)
    except HTTPException:
        raise
    except (FirebaseError, ValueError, TypeError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="The sign-in token is invalid or expired") from error

    return Identity(
        uid=str(claims["uid"]),
        email=claims.get("email"),
        name=claims.get("name"),
        claims=claims,
    )


def get_current_admin(
    identity: Identity = Depends(get_current_identity),
    session: Session = Depends(get_session),
) -> AdminIdentity:
    settings = get_settings()
    account = session.scalar(select(AdminAccount).where(AdminAccount.firebase_uid == identity.uid))
    if account is not None:
        if not account.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not authorized for the CMS")
        return AdminIdentity(account.firebase_uid, account.email or identity.email, account.display_name or identity.name, account.role)

    if identity.uid in settings.bootstrap_admin_uids:
        return AdminIdentity(identity.uid, identity.email, identity.name, "super_admin")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is not authorized for the CMS")


def require_admin_roles(*roles: str):
    def dependency(admin: AdminIdentity = Depends(get_current_admin)) -> AdminIdentity:
        if admin.role != "super_admin" and admin.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action")
        return admin

    return dependency
