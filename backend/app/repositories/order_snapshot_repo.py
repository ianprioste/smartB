"""Repository for persistent Bling order snapshots and sync state."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import re

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models.database import BlingOrderSnapshotModel, BlingOrdersSyncStateModel
from app.infra.logging import get_logger
from app.utils.datetime_utils import now_local

logger = get_logger(__name__)


# Status name mapping
# Bling situacao.valor categories: 0=Em aberto, 1=Atendido, 2=Cancelado.
_VALOR_LABEL = {0: "Em aberto", 1: "Atendido", 2: "Cancelado"}

KNOWN_STATUSES = [
    {"id": 6, "nome": "Em aberto"},
    {"id": 9, "nome": "Atendido"},
    {"id": 15, "nome": "Cancelado"},
]
STATUS_NAME_MAP = {
    6: "Em aberto",
    9: "Atendido",
    12: "Cancelado",
    15: "Cancelado",
}
VALID_STATUS_NAMES = {"Em aberto", "Atendido", "Cancelado"}


def _normalize_status_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return name
    lower = name.strip().lower()
    if "atendid" in lower or "entreg" in lower:
        return "Atendido"
    if "cancel" in lower or "conclu" in lower or "devolv" in lower:
        return "Cancelado"
    if "pendente" in lower:
        return "Em aberto"
    return name


def _resolve_status_name(situacao: Dict[str, Any], status_id: Optional[int], persisted_status_name: Optional[str] = None) -> Optional[str]:
    # Prefer valor (category) — always semantically correct.
    if isinstance(situacao, dict):
        valor = situacao.get("valor")
        if valor is not None:
            try:
                label = _VALOR_LABEL.get(int(valor))
                if label:
                    return label
            except (TypeError, ValueError):
                pass

        name = situacao.get("nome")
        if name:
            return _normalize_status_name(str(name))

    if persisted_status_name:
        normalized = _normalize_status_name(persisted_status_name)
        if normalized in VALID_STATUS_NAMES:
            return normalized

    if status_id is not None:
        return STATUS_NAME_MAP.get(status_id, f"Status {status_id}")

    return None


def _extract_customer_email(order_list_payload: Dict[str, Any], order_detail_payload: Dict[str, Any]) -> Optional[str]:
    detail_data = order_detail_payload.get("data") if isinstance(order_detail_payload.get("data"), dict) else {}
    detail_contato = detail_data.get("contato") if isinstance(detail_data.get("contato"), dict) else {}
    detail_cliente = detail_data.get("cliente") if isinstance(detail_data.get("cliente"), dict) else {}
    list_contato = order_list_payload.get("contato") if isinstance(order_list_payload.get("contato"), dict) else {}
    list_cliente = order_list_payload.get("cliente") if isinstance(order_list_payload.get("cliente"), dict) else {}

    candidates = [
        detail_contato.get("email"),
        detail_cliente.get("email"),
        detail_data.get("email"),
        detail_data.get("emailContato"),
        list_contato.get("email"),
        list_cliente.get("email"),
        order_list_payload.get("email"),
        order_list_payload.get("emailContato"),
    ]

    for candidate in candidates:
        text = str(candidate or "").strip()
        if text and "@" in text:
            return text

    return None


def _extract_customer_contact_id(order_list_payload: Dict[str, Any], order_detail_payload: Dict[str, Any]) -> Optional[int]:
    detail_data = order_detail_payload.get("data") if isinstance(order_detail_payload.get("data"), dict) else {}
    detail_contato = detail_data.get("contato") if isinstance(detail_data.get("contato"), dict) else {}
    list_contato = order_list_payload.get("contato") if isinstance(order_list_payload.get("contato"), dict) else {}

    candidates = [
        detail_contato.get("id"),
        detail_data.get("idContato"),
        detail_data.get("contatoId"),
        list_contato.get("id"),
        order_list_payload.get("idContato"),
        order_list_payload.get("contatoId"),
    ]

    for candidate in candidates:
        contact_id = _try_int(candidate)
        if contact_id is not None:
            return contact_id

    return None


class OrderSnapshotRepository:
    @staticmethod
    def count_by_tenant(db: Session, tenant_id: UUID) -> int:
        return db.query(BlingOrderSnapshotModel).filter(BlingOrderSnapshotModel.tenant_id == tenant_id).count()

    @staticmethod
    def upsert_order(
        db: Session,
        tenant_id: UUID,
        order_list_payload: Dict[str, Any],
        order_detail_payload: Dict[str, Any],
    ) -> None:
        order_id = order_list_payload.get("id")
        if order_id is None:
            return

        existing = (
            db.query(BlingOrderSnapshotModel)
            .filter(
                BlingOrderSnapshotModel.tenant_id == tenant_id,
                BlingOrderSnapshotModel.bling_order_id == int(order_id),
            )
            .first()
        )

        situacao = order_list_payload.get("situacao") if isinstance(order_list_payload.get("situacao"), dict) else {}
        contato = order_list_payload.get("contato") if isinstance(order_list_payload.get("contato"), dict) else {}

        row = existing or BlingOrderSnapshotModel(
            tenant_id=tenant_id,
            bling_order_id=int(order_id),
            imported_at=datetime.utcnow(),
        )

        row.numero = order_list_payload.get("numero")
        row.numero_loja = order_list_payload.get("numeroLoja")
        row.order_date = _try_parse_datetime(order_list_payload.get("data"))
        row.customer_name = contato.get("nome") if isinstance(contato, dict) else None
        # Only overwrite customer_email if the new value is not empty;
        # preserve enriched emails (fetched from /contatos API) across syncs.
        extracted_email = _extract_customer_email(order_list_payload, order_detail_payload)
        if extracted_email:
            row.customer_email = extracted_email
        elif not existing:
            row.customer_email = None
        row.customer_contact_id = _extract_customer_contact_id(order_list_payload, order_detail_payload)

        detail_data = order_detail_payload.get("data") if isinstance(order_detail_payload.get("data"), dict) else {}
        detail_situacao = detail_data.get("situacao") if isinstance(detail_data.get("situacao"), dict) else {}
        effective_situacao = situacao if isinstance(situacao, dict) and situacao else detail_situacao
        
        # Extract status_id
        if isinstance(effective_situacao, dict) and effective_situacao.get("id"):
            row.status_id = _try_int(effective_situacao.get("id"))
        else:
            row.status_id = _try_int(order_list_payload.get("situacao"))

        persisted_status_name = existing.status_name if existing and existing.status_id == row.status_id else None
        row.status_name = _resolve_status_name(effective_situacao, row.status_id, persisted_status_name)
        
        # Log para diagnóstico
        logger.info(
            "order_upsert order_id=%s numero=%s status_id=%s status_name=%s raw_situacao=%s",
            order_id,
            row.numero,
            row.status_id,
            row.status_name,
            str(effective_situacao)[:200],
        )
        
        row.total_value = _extract_paid_total(order_detail_payload, order_list_payload)

        row.raw_order = order_list_payload
        row.raw_detail = order_detail_payload
        row.source_updated_at = _extract_source_updated_at(order_detail_payload) or _try_parse_datetime(order_list_payload.get("data"))
        row.updated_at = datetime.utcnow()

        if existing is None:
            db.add(row)

    @staticmethod
    def list_for_orders_page(
        db: Session,
        tenant_id: UUID,
        status_ids: List[int],
        search: str,
    ) -> List[BlingOrderSnapshotModel]:
        query = db.query(BlingOrderSnapshotModel).filter(BlingOrderSnapshotModel.tenant_id == tenant_id)

        if status_ids:
            query = query.filter(BlingOrderSnapshotModel.status_id.in_(status_ids))

        term = (search or "").strip().lower()
        if term:
            if not term.isdigit():
                query = query.filter(
                    or_(
                        BlingOrderSnapshotModel.customer_name.ilike(f"%{term}%"),
                        BlingOrderSnapshotModel.numero_loja.ilike(f"%{term}%"),
                    )
                )
            # numeric match on numero can be checked in python for portability

        rows = query.order_by(BlingOrderSnapshotModel.order_date.desc().nullslast()).all()

        if term and term.isdigit():
            rows = [
                row for row in rows
                if term in str(row.numero or "") or term in str(row.bling_order_id or "")
            ]

        return rows

    @staticmethod
    def list_distinct_statuses(db: Session, tenant_id: UUID) -> List[Dict[str, Any]]:
        """Return distinct (status_id, status_name) pairs from persisted snapshots."""
        rows = (
            db.query(
                BlingOrderSnapshotModel.status_id,
                BlingOrderSnapshotModel.status_name,
            )
            .filter(
                BlingOrderSnapshotModel.tenant_id == tenant_id,
                BlingOrderSnapshotModel.status_id.isnot(None),
            )
            .distinct()
            .all()
        )
        return [
            {"id": r.status_id, "nome": r.status_name or f"Status {r.status_id}"}
            for r in rows
            if r.status_id is not None
        ]

    @staticmethod
    def list_for_period(db: Session, tenant_id: UUID, start_dt: datetime, end_dt: datetime) -> List[BlingOrderSnapshotModel]:
        return (
            db.query(BlingOrderSnapshotModel)
            .filter(
                BlingOrderSnapshotModel.tenant_id == tenant_id,
                BlingOrderSnapshotModel.order_date >= start_dt,
                BlingOrderSnapshotModel.order_date <= end_dt,
            )
            .order_by(BlingOrderSnapshotModel.order_date.desc().nullslast())
            .all()
        )

    @staticmethod
    def list_status_updates_since(
        db: Session,
        tenant_id: UUID,
        since: datetime,
    ) -> List[BlingOrderSnapshotModel]:
        return (
            db.query(BlingOrderSnapshotModel)
            .filter(
                BlingOrderSnapshotModel.tenant_id == tenant_id,
                BlingOrderSnapshotModel.updated_at > since,
            )
            .order_by(BlingOrderSnapshotModel.updated_at.asc())
            .all()
        )

    @staticmethod
    def get_sync_state(db: Session, tenant_id: UUID) -> Optional[BlingOrdersSyncStateModel]:
        return (
            db.query(BlingOrdersSyncStateModel)
            .filter(BlingOrdersSyncStateModel.tenant_id == tenant_id)
            .first()
        )

    @staticmethod
    def get_snapshot_stats(db: Session, tenant_id: UUID) -> Dict[str, Any]:
        total = (
            db.query(func.count(BlingOrderSnapshotModel.id))
            .filter(BlingOrderSnapshotModel.tenant_id == tenant_id)
            .scalar()
        ) or 0

        latest_order_date = (
            db.query(func.max(BlingOrderSnapshotModel.order_date))
            .filter(BlingOrderSnapshotModel.tenant_id == tenant_id)
            .scalar()
        )

        latest_imported_at = (
            db.query(func.max(BlingOrderSnapshotModel.imported_at))
            .filter(BlingOrderSnapshotModel.tenant_id == tenant_id)
            .scalar()
        )

        latest_updated_at = (
            db.query(func.max(BlingOrderSnapshotModel.updated_at))
            .filter(BlingOrderSnapshotModel.tenant_id == tenant_id)
            .scalar()
        )

        return {
            "total_orders": int(total),
            "latest_order_date": latest_order_date,
            "latest_imported_at": latest_imported_at,
            "latest_updated_at": latest_updated_at,
        }

    @staticmethod
    def list_missing_customer_email(
        db: Session,
        tenant_id: UUID,
        limit: int = 20,
    ) -> List[BlingOrderSnapshotModel]:
        safe_limit = max(1, int(limit))
        return (
            db.query(BlingOrderSnapshotModel)
            .filter(
                BlingOrderSnapshotModel.tenant_id == tenant_id,
                BlingOrderSnapshotModel.customer_contact_id.isnot(None),
                or_(
                    BlingOrderSnapshotModel.customer_email.is_(None),
                    BlingOrderSnapshotModel.customer_email == "",
                ),
            )
            .order_by(BlingOrderSnapshotModel.updated_at.asc())
            .limit(safe_limit)
            .all()
        )

    @staticmethod
    def apply_customer_emails_by_contact_id(
        db: Session,
        tenant_id: UUID,
        email_map: Dict[int, str],
    ) -> int:
        updated = 0
        for contact_id, email in email_map.items():
            normalized = str(email or "").strip()
            if not normalized:
                continue
            rows = (
                db.query(BlingOrderSnapshotModel)
                .filter(
                    BlingOrderSnapshotModel.tenant_id == tenant_id,
                    BlingOrderSnapshotModel.customer_contact_id == int(contact_id),
                    or_(
                        BlingOrderSnapshotModel.customer_email.is_(None),
                        BlingOrderSnapshotModel.customer_email == "",
                    ),
                )
                .all()
            )
            for row in rows:
                row.customer_email = normalized
                row.updated_at = datetime.utcnow()
                updated += 1
        return updated

    @staticmethod
    def get_or_create_sync_state(db: Session, tenant_id: UUID) -> BlingOrdersSyncStateModel:
        state = (
            db.query(BlingOrdersSyncStateModel)
            .filter(BlingOrdersSyncStateModel.tenant_id == tenant_id)
            .first()
        )
        if state:
            return state

        state = BlingOrdersSyncStateModel(
            tenant_id=tenant_id,
            last_sync_status="never",
            last_sync_message="No sync executed yet",
        )
        db.add(state)
        db.flush()
        return state

    @staticmethod
    def mark_sync_success(db: Session, tenant_id: UUID, mode: str, message: str) -> None:
        state = OrderSnapshotRepository.get_or_create_sync_state(db, tenant_id)
        now = now_local()
        if mode == "full":
            state.last_full_sync_at = now
        else:
            state.last_incremental_sync_at = now
        state.last_successful_sync_at = now
        state.last_sync_status = "ok"
        state.last_sync_message = message
        state.updated_at = now

    @staticmethod
    def mark_sync_running(db: Session, tenant_id: UUID, mode: str, message: str) -> None:
        state = OrderSnapshotRepository.get_or_create_sync_state(db, tenant_id)
        state.last_sync_status = "running"
        state.last_sync_message = f"mode={mode}|{message}"
        state.updated_at = now_local()

    @staticmethod
    def mark_sync_failure(db: Session, tenant_id: UUID, message: str) -> None:
        state = OrderSnapshotRepository.get_or_create_sync_state(db, tenant_id)
        state.last_sync_status = "error"
        state.last_sync_message = message
        state.updated_at = now_local()


def _try_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _extract_paid_total(order_detail_payload: Dict[str, Any], order_list_payload: Dict[str, Any]) -> Optional[float]:
    for payload in (order_detail_payload, order_list_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total = _try_float(data.get("total"))
        if total is not None and total > 0:
            return total

    for payload in (order_detail_payload, order_list_payload):
        if not isinstance(payload, dict):
            continue
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        total_products = _try_float(data.get("totalProdutos"))
        if total_products is not None:
            return total_products

    return None


def _try_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _try_parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_source_updated_at(order_detail_payload: Dict[str, Any]) -> Optional[datetime]:
    if not isinstance(order_detail_payload, dict):
        return None
    data = order_detail_payload.get("data") if isinstance(order_detail_payload.get("data"), dict) else order_detail_payload
    for key in ("dataAlteracao", "updatedAt", "atualizadoEm", "data"):
        parsed = _try_parse_datetime(data.get(key)) if isinstance(data, dict) else None
        if parsed is not None:
            return parsed
    return None


def parse_progress_from_sync_message(message: Optional[str]) -> Dict[str, Any]:
    """Extract numeric progress from sync state message payload.

    Expected format: mode=<mode>|processed=<n>|total=<n>|upserted=<n>|failed=<n>
    """
    text = (message or "").strip()
    if not text:
        return {
            "mode": None,
            "processed": 0,
            "total": 0,
            "upserted": 0,
            "failed": 0,
            "percent": 0,
        }

    def _num(name: str) -> int:
        m = re.search(rf"(?:^|\|){name}=(\d+)", text)
        return int(m.group(1)) if m else 0

    m_mode = re.search(r"(?:^|\|)mode=([^|]+)", text)
    mode = m_mode.group(1) if m_mode else None
    processed = _num("processed")
    total = _num("total")
    upserted = _num("upserted")
    failed = _num("failed")
    percent = int((processed / total) * 100) if total > 0 else 0
    if percent > 100:
        percent = 100

    return {
        "mode": mode,
        "processed": processed,
        "total": total,
        "upserted": upserted,
        "failed": failed,
        "percent": percent,
    }