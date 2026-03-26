"""Repository for access control (profiles, allowed emails, sessions)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.database import AccessProfileModel, AccessUserModel, AccessSessionModel

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AccessRepository:
    @staticmethod
    def get_or_create_admin_profile(db: Session, tenant_id: UUID) -> AccessProfileModel:
        profile = (
            db.query(AccessProfileModel)
            .filter(
                AccessProfileModel.tenant_id == tenant_id,
                AccessProfileModel.name == "Administrador",
                AccessProfileModel.is_active.is_(True),
            )
            .first()
        )
        if profile:
            return profile

        profile = AccessProfileModel(
            tenant_id=tenant_id,
            name="Administrador",
            description="Acesso total ao sistema",
            permissions={"all": True},
            is_active=True,
        )
        db.add(profile)
        db.flush()
        return profile

    @staticmethod
    def count_users(db: Session, tenant_id: UUID) -> int:
        return (
            db.query(AccessUserModel)
            .filter(AccessUserModel.tenant_id == tenant_id)
            .count()
        )

    @staticmethod
    def list_profiles(db: Session, tenant_id: UUID):
        return (
            db.query(AccessProfileModel)
            .filter(AccessProfileModel.tenant_id == tenant_id)
            .order_by(AccessProfileModel.name.asc())
            .all()
        )

    @staticmethod
    def create_profile(
        db: Session,
        tenant_id: UUID,
        name: str,
        description: Optional[str],
        permissions: Optional[dict],
    ) -> AccessProfileModel:
        profile = AccessProfileModel(
            tenant_id=tenant_id,
            name=name,
            description=description,
            permissions=permissions or {},
            is_active=True,
        )
        db.add(profile)
        db.flush()
        return profile

    @staticmethod
    def update_profile(
        db: Session,
        tenant_id: UUID,
        profile_id: UUID,
        name: Optional[str],
        description: Optional[str],
        permissions: Optional[dict],
        is_active: Optional[bool],
    ) -> Optional[AccessProfileModel]:
        profile = (
            db.query(AccessProfileModel)
            .filter(
                AccessProfileModel.tenant_id == tenant_id,
                AccessProfileModel.id == profile_id,
            )
            .first()
        )
        if not profile:
            return None

        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description
        if permissions is not None:
            profile.permissions = permissions
        if is_active is not None:
            profile.is_active = is_active
        profile.updated_at = datetime.utcnow()
        return profile

    @staticmethod
    def delete_profile(db: Session, tenant_id: UUID, profile_id: UUID) -> bool:
        assigned = (
            db.query(AccessUserModel)
            .filter(
                AccessUserModel.tenant_id == tenant_id,
                AccessUserModel.profile_id == profile_id,
            )
            .count()
        )
        if assigned > 0:
            return False

        profile = (
            db.query(AccessProfileModel)
            .filter(
                AccessProfileModel.tenant_id == tenant_id,
                AccessProfileModel.id == profile_id,
            )
            .first()
        )
        if not profile:
            return False

        db.delete(profile)
        return True

    @staticmethod
    def list_users(db: Session, tenant_id: UUID):
        return (
            db.query(AccessUserModel)
            .filter(AccessUserModel.tenant_id == tenant_id)
            .order_by(AccessUserModel.email.asc())
            .all()
        )

    @staticmethod
    def get_user_by_email(db: Session, tenant_id: UUID, email: str) -> Optional[AccessUserModel]:
        return (
            db.query(AccessUserModel)
            .filter(
                AccessUserModel.tenant_id == tenant_id,
                AccessUserModel.email == email.strip().lower(),
            )
            .first()
        )

    @staticmethod
    def hash_password(password: str) -> str:
        return _pwd_context.hash(password)

    @staticmethod
    def verify_password(plain: str, hashed: Optional[str]) -> bool:
        if not hashed:
            return False
        return _pwd_context.verify(plain, hashed)

    @staticmethod
    def set_password(db: Session, user: AccessUserModel, password: str) -> None:
        user.password_hash = _pwd_context.hash(password)
        user.updated_at = datetime.utcnow()

    @staticmethod
    def create_user(
        db: Session,
        tenant_id: UUID,
        email: str,
        profile_id: UUID,
        is_active: bool = True,
        password: Optional[str] = None,
    ) -> AccessUserModel:
        user = AccessUserModel(
            tenant_id=tenant_id,
            email=email.strip().lower(),
            password_hash=_pwd_context.hash(password) if password else None,
            profile_id=profile_id,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def update_user(
        db: Session,
        tenant_id: UUID,
        user_id: UUID,
        profile_id: Optional[UUID],
        is_active: Optional[bool],
    ) -> Optional[AccessUserModel]:
        user = (
            db.query(AccessUserModel)
            .filter(
                AccessUserModel.tenant_id == tenant_id,
                AccessUserModel.id == user_id,
            )
            .first()
        )
        if not user:
            return None

        if profile_id is not None:
            user.profile_id = profile_id
        if is_active is not None:
            user.is_active = is_active
        user.updated_at = datetime.utcnow()
        return user

    @staticmethod
    def delete_user(db: Session, tenant_id: UUID, user_id: UUID) -> bool:
        user = (
            db.query(AccessUserModel)
            .filter(
                AccessUserModel.tenant_id == tenant_id,
                AccessUserModel.id == user_id,
            )
            .first()
        )
        if not user:
            return False

        db.query(AccessSessionModel).filter(AccessSessionModel.user_id == user.id).delete()
        db.delete(user)
        return True

    @staticmethod
    def create_session(db: Session, user: AccessUserModel, ttl_hours: int = 12) -> AccessSessionModel:
        token = str(uuid.uuid4()) + str(uuid.uuid4())
        session = AccessSessionModel(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(session)
        db.flush()
        return session

    @staticmethod
    def get_session(db: Session, token: str) -> Optional[AccessSessionModel]:
        return (
            db.query(AccessSessionModel)
            .filter(
                AccessSessionModel.token == token,
                AccessSessionModel.expires_at > datetime.utcnow(),
            )
            .first()
        )

    @staticmethod
    def get_session_user(db: Session, token: str) -> Optional[AccessUserModel]:
        session = AccessRepository.get_session(db, token)
        if not session:
            return None

        user = (
            db.query(AccessUserModel)
            .filter(AccessUserModel.id == session.user_id)
            .first()
        )
        if not user or not user.is_active:
            return None

        return user

    @staticmethod
    def revoke_session(db: Session, token: str) -> None:
        db.query(AccessSessionModel).filter(AccessSessionModel.token == token).delete()

    @staticmethod
    def revoke_user_sessions(db: Session, user_id: UUID) -> None:
        db.query(AccessSessionModel).filter(AccessSessionModel.user_id == user_id).delete()
