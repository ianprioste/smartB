"""Application access control: email allowlist and access profiles."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.infra.logging import get_logger
from app.models.schemas import PasswordResetRequest, PasswordResetCodeVerifyRequest, PasswordResetConfirmRequest, SimpleMessageResponse
from app.repositories.access_repo import AccessRepository
from app.services.email_service import EmailService
from app.settings import settings

router = APIRouter(prefix="/auth/access", tags=["access-control"])
logger = get_logger(__name__)

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
SESSION_COOKIE = "smartb_session"


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        email = (v or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("E-mail inválido")
        return email

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        password = (v or "").strip()
        if len(password) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return password


class ProfileCreateRequest(BaseModel):
    name: str
    description: str | None = None


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AccessUserCreateRequest(BaseModel):
    email: str
    profile_id: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        email = (v or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("E-mail inválido")
        return email

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        password = (v or "").strip()
        if len(password) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return password


class AccessUserUpdateRequest(BaseModel):
    profile_id: str | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return None
        password = v.strip()
        if len(password) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return password


def _ensure_admin_bootstrap(db: Session) -> None:
    AccessRepository.get_or_create_admin_profile(db, DEFAULT_TENANT_ID)


def _require_admin(request: Request, db: Session) -> None:
    access_user = getattr(request.state, "access_user", None)
    if not access_user:
        raise HTTPException(status_code=401, detail="Não autenticado")

    profile = next(
        (p for p in AccessRepository.list_profiles(db, DEFAULT_TENANT_ID) if p.id == access_user.profile_id),
        None,
    )
    if not profile or profile.name != "Administrador":
        raise HTTPException(status_code=403, detail="Apenas administradores podem gerenciar acessos")


@router.get("/bootstrap-status")
async def bootstrap_status(db: Session = Depends(get_db)):
    _ensure_admin_bootstrap(db)
    total_users = AccessRepository.count_users(db, DEFAULT_TENANT_ID)
    return {
        "needs_bootstrap": total_users == 0,
        "master_admin_email": settings.MASTER_ADMIN_EMAIL,
    }


def _get_active_reset_for_email(db: Session, email: str):
    user = AccessRepository.get_user_by_email(db, DEFAULT_TENANT_ID, email)
    if not user or not user.is_active:
        return None, None
    return user, AccessRepository.get_active_password_reset_code(db, user.id)


@router.post("/forgot-password/request", response_model=SimpleMessageResponse)
async def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    _ensure_admin_bootstrap(db)
    email = payload.email.strip().lower()
    user = AccessRepository.get_user_by_email(db, DEFAULT_TENANT_ID, email)

    # Avoid user enumeration: always return a generic success message.
    if user is None or not user.is_active:
        logger.info("password_reset_requested_unknown_email email=%s", email)
        return SimpleMessageResponse(message="Se o e-mail existir, enviaremos um código de recuperação")

    code = AccessRepository.generate_password_reset_code()
    AccessRepository.create_password_reset_code(
        db=db,
        tenant_id=DEFAULT_TENANT_ID,
        user_id=user.id,
        email=email,
        code=code,
        expires_minutes=settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES,
    )
    try:
        EmailService.send_password_reset_code(
            to_email=email,
            code=code,
            expires_minutes=settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES,
        )
    except Exception as exc:
        db.rollback()
        logger.error("password_reset_email_failed email=%s error=%s", email, str(exc))
        raise HTTPException(status_code=500, detail="Falha ao enviar o código de recuperação")
    db.commit()
    logger.info("password_reset_requested email=%s", email)
    return SimpleMessageResponse(message="Se o e-mail existir, enviaremos um código de recuperação")


@router.post("/forgot-password/verify", response_model=SimpleMessageResponse)
async def verify_password_reset_code(payload: PasswordResetCodeVerifyRequest, db: Session = Depends(get_db)):
    user, reset_code = _get_active_reset_for_email(db, payload.email)
    if not user or not reset_code:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    is_valid = AccessRepository.verify_password_reset_code(db, reset_code, payload.email, payload.code)
    db.commit()
    if not is_valid:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    return SimpleMessageResponse(message="Código validado com sucesso")


@router.post("/forgot-password/reset", response_model=SimpleMessageResponse)
async def reset_password_with_code(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    user, reset_code = _get_active_reset_for_email(db, payload.email)
    if not user or not reset_code:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    is_valid = AccessRepository.verify_password_reset_code(db, reset_code, payload.email, payload.code)
    if not is_valid:
        db.commit()
        raise HTTPException(status_code=400, detail="Código inválido ou expirado")

    AccessRepository.set_password(db, user, payload.new_password)
    AccessRepository.mark_password_reset_code_used(reset_code)
    AccessRepository.invalidate_password_reset_codes(db, user.id)
    AccessRepository.revoke_user_sessions(db, user.id)
    db.commit()
    logger.info("password_reset_completed email=%s", payload.email)
    return SimpleMessageResponse(message="Senha alterada com sucesso")


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    _ensure_admin_bootstrap(db)
    email = payload.email.strip().lower()
    password = payload.password

    user = AccessRepository.get_user_by_email(db, DEFAULT_TENANT_ID, email)

    # First access bootstrap: only MASTER_ADMIN_EMAIL can become first admin.
    if user is None and AccessRepository.count_users(db, DEFAULT_TENANT_ID) == 0:
        if email != settings.MASTER_ADMIN_EMAIL:
            raise HTTPException(
                status_code=403,
                detail=f"Primeiro acesso permitido apenas para o administrador master ({settings.MASTER_ADMIN_EMAIL})",
            )
        admin = AccessRepository.get_or_create_admin_profile(db, DEFAULT_TENANT_ID)
        user = AccessRepository.create_user(
            db,
            tenant_id=DEFAULT_TENANT_ID,
            email=email,
            profile_id=admin.id,
            is_active=True,
            password=password,
        )

    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Este e-mail não está autorizado a acessar o app")

    if not AccessRepository.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")

    profile = next((p for p in AccessRepository.list_profiles(db, DEFAULT_TENANT_ID) if p.id == user.profile_id), None)
    if not profile or not profile.is_active:
        raise HTTPException(status_code=403, detail="Perfil de acesso inativo")

    # TTL: 30 days if remember_me, 12 hours otherwise
    ttl_hours = 30 * 24 if payload.remember_me else 12
    session = AccessRepository.create_session(db, user, ttl_hours=ttl_hours)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * ttl_hours,
    )

    return {
        "ok": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "profile": {
                "id": str(profile.id),
                "name": profile.name,
            },
        },
    }


@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        AccessRepository.revoke_session(db, token)
        db.commit()
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
async def me(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")

    user = AccessRepository.get_session_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Sessão inválida")

    profile = next((p for p in AccessRepository.list_profiles(db, DEFAULT_TENANT_ID) if p.id == user.profile_id), None)
    if not profile:
        raise HTTPException(status_code=401, detail="Perfil inválido")

    return {
        "ok": True,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "profile": {
                "id": str(profile.id),
                "name": profile.name,
            },
        },
    }


@router.get("/profiles")
async def list_profiles(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    _ensure_admin_bootstrap(db)
    profiles = AccessRepository.list_profiles(db, DEFAULT_TENANT_ID)
    return {
        "data": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in profiles
        ]
    }


@router.post("/profiles")
async def create_profile(payload: ProfileCreateRequest, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    _ensure_admin_bootstrap(db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome do perfil é obrigatório")

    profile = AccessRepository.create_profile(
        db,
        tenant_id=DEFAULT_TENANT_ID,
        name=name,
        description=(payload.description or "").strip() or None,
        permissions={},
    )
    db.commit()

    return {
        "id": str(profile.id),
        "name": profile.name,
        "description": profile.description,
        "is_active": profile.is_active,
    }


@router.patch("/profiles/{profile_id}")
async def update_profile(profile_id: str, payload: ProfileUpdateRequest, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    profile = AccessRepository.update_profile(
        db,
        tenant_id=DEFAULT_TENANT_ID,
        profile_id=UUID(profile_id),
        name=payload.name.strip() if payload.name else None,
        description=(payload.description or "").strip() if payload.description is not None else None,
        permissions=None,
        is_active=payload.is_active,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    db.commit()
    return {"ok": True}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    success = AccessRepository.delete_profile(db, DEFAULT_TENANT_ID, UUID(profile_id))
    if not success:
        raise HTTPException(status_code=400, detail="Não foi possível remover perfil (pode estar em uso)")

    db.commit()
    return {"ok": True}


@router.get("/users")
async def list_users(request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    users = AccessRepository.list_users(db, DEFAULT_TENANT_ID)
    profiles = {p.id: p for p in AccessRepository.list_profiles(db, DEFAULT_TENANT_ID)}
    return {
        "data": [
            {
                "id": str(u.id),
                "email": u.email,
                "is_active": u.is_active,
                "profile": {
                    "id": str(u.profile_id),
                    "name": profiles[u.profile_id].name if u.profile_id in profiles else "—",
                },
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
            for u in users
        ]
    }


@router.post("/users")
async def create_user(payload: AccessUserCreateRequest, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    email = payload.email.strip().lower()
    profile_id = UUID(payload.profile_id)

    exists = AccessRepository.get_user_by_email(db, DEFAULT_TENANT_ID, email)
    if exists:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    user = AccessRepository.create_user(
        db,
        tenant_id=DEFAULT_TENANT_ID,
        email=email,
        profile_id=profile_id,
        is_active=True,
        password=payload.password,
    )
    db.commit()

    return {
        "id": str(user.id),
        "email": user.email,
        "is_active": user.is_active,
    }


@router.patch("/users/{user_id}")
async def update_user(user_id: str, payload: AccessUserUpdateRequest, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    profile_id = UUID(payload.profile_id) if payload.profile_id else None
    user = AccessRepository.update_user(
        db,
        tenant_id=DEFAULT_TENANT_ID,
        user_id=UUID(user_id),
        profile_id=profile_id,
        is_active=payload.is_active,
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if payload.password:
        AccessRepository.set_password(db, user, payload.password)
        AccessRepository.revoke_user_sessions(db, user.id)

    if payload.is_active is False:
        AccessRepository.revoke_user_sessions(db, user.id)

    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    _require_admin(request, db)
    success = AccessRepository.delete_user(db, DEFAULT_TENANT_ID, UUID(user_id))
    if not success:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    db.commit()
    return {"ok": True}
