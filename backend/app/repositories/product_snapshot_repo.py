"""Repository for persistent Bling product snapshots."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import BlingProductSnapshotModel


class ProductSnapshotRepository:
    @staticmethod
    def upsert_product_detail(
        db: Session,
        tenant_id: UUID,
        product_payload: Dict[str, Any],
    ) -> None:
        product_data = product_payload.get("data") if isinstance(product_payload.get("data"), dict) else product_payload
        if not isinstance(product_data, dict):
            return

        product_id = product_data.get("id")
        if product_id is None:
            return

        product_id = int(product_id)
        existing = (
            db.query(BlingProductSnapshotModel)
            .filter(
                BlingProductSnapshotModel.tenant_id == tenant_id,
                BlingProductSnapshotModel.bling_product_id == product_id,
            )
            .first()
        )

        row = existing or BlingProductSnapshotModel(
            tenant_id=tenant_id,
            bling_product_id=product_id,
            imported_at=datetime.utcnow(),
        )

        row.codigo = product_data.get("codigo")
        row.nome = product_data.get("nome")
        row.formato = product_data.get("formato")
        row.situacao = product_data.get("situacao")
        row.parent_product_id = _extract_parent_id(product_data)
        row.stock_quantity = _extract_stock_quantity(product_data)
        row.raw_payload = product_payload
        row.source_updated_at = _extract_source_updated_at(product_data)
        row.updated_at = datetime.utcnow()

        if existing is None:
            db.add(row)

    @staticmethod
    def list_all(db: Session, tenant_id: UUID) -> List[BlingProductSnapshotModel]:
        return (
            db.query(BlingProductSnapshotModel)
            .filter(BlingProductSnapshotModel.tenant_id == tenant_id)
            .order_by(BlingProductSnapshotModel.nome.asc())
            .all()
        )

    @staticmethod
    def list_by_query(db: Session, tenant_id: UUID, q: str) -> List[BlingProductSnapshotModel]:
        term = (q or "").strip()
        if not term:
            return ProductSnapshotRepository.list_all(db, tenant_id)

        if term.isdigit():
            return (
                db.query(BlingProductSnapshotModel)
                .filter(
                    BlingProductSnapshotModel.tenant_id == tenant_id,
                    or_(
                        BlingProductSnapshotModel.bling_product_id == int(term),
                        BlingProductSnapshotModel.codigo.ilike(f"%{term}%"),
                        BlingProductSnapshotModel.nome.ilike(f"%{term}%"),
                    ),
                )
                .order_by(BlingProductSnapshotModel.nome.asc())
                .all()
            )

        return (
            db.query(BlingProductSnapshotModel)
            .filter(
                BlingProductSnapshotModel.tenant_id == tenant_id,
                or_(
                    BlingProductSnapshotModel.codigo.ilike(f"%{term}%"),
                    BlingProductSnapshotModel.nome.ilike(f"%{term}%"),
                ),
            )
            .order_by(BlingProductSnapshotModel.nome.asc())
            .all()
        )

    @staticmethod
    def list_children_by_parent_ids(
        db: Session,
        tenant_id: UUID,
        parent_ids: List[int],
    ) -> List[BlingProductSnapshotModel]:
        normalized_ids = [int(pid) for pid in parent_ids if pid is not None]
        if not normalized_ids:
            return []

        return (
            db.query(BlingProductSnapshotModel)
            .filter(
                BlingProductSnapshotModel.tenant_id == tenant_id,
                BlingProductSnapshotModel.parent_product_id.in_(normalized_ids),
            )
            .order_by(BlingProductSnapshotModel.parent_product_id.asc(), BlingProductSnapshotModel.nome.asc())
            .all()
        )


def _extract_parent_id(product_data: Dict[str, Any]) -> Optional[int]:
    variacao = product_data.get("variacao") if isinstance(product_data.get("variacao"), dict) else {}
    produto_pai = variacao.get("produtoPai") if isinstance(variacao.get("produtoPai"), dict) else {}
    candidate = produto_pai.get("id") or product_data.get("idProdutoPai") or product_data.get("pai")
    try:
        return int(candidate) if candidate is not None else None
    except Exception:
        return None


def _extract_stock_quantity(product_data: Dict[str, Any]) -> Optional[float]:
    estoque = product_data.get("estoque") if isinstance(product_data.get("estoque"), dict) else {}
    saldo = product_data.get("saldoEstoque") if isinstance(product_data.get("saldoEstoque"), dict) else {}

    candidates = [
        product_data.get("quantidade"),
        product_data.get("estoqueAtual"),
        product_data.get("saldo"),
        product_data.get("saldoVirtualTotal"),
        product_data.get("saldoFisicoTotal"),
        estoque.get("quantidade"),
        estoque.get("saldoVirtualTotal"),
        estoque.get("saldoFisicoTotal"),
        saldo.get("saldoVirtualTotal"),
        saldo.get("saldoFisicoTotal"),
    ]

    for value in candidates:
        try:
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def _extract_source_updated_at(product_data: Dict[str, Any]):
    from app.repositories.order_snapshot_repo import _try_parse_datetime

    for key in ("dataAlteracao", "updatedAt", "atualizadoEm", "data"):
        parsed = _try_parse_datetime(product_data.get(key))
        if parsed is not None:
            return parsed
    return None
