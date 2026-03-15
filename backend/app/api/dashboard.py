"""Dashboard summary endpoint – aggregates indicators for the home page."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from app.infra.db import get_db
from app.infra.bling_client import BlingClient, BlingAuthError
from app.infra.logging import get_logger
from app.repositories.bling_token_repo import BlingTokenRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")

# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #

def _fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _make_client(db: Session):
    """Return a BlingClient if a token exists, else None."""
    token_row = BlingTokenRepository.get_by_tenant(db, DEFAULT_TENANT_ID)
    if not token_row:
        return None

    def _save(access_token, refresh_token, expires_at):
        BlingTokenRepository.create_or_update(
            db=db,
            tenant_id=DEFAULT_TENANT_ID,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )

    return BlingClient(
        access_token=token_row.access_token,
        refresh_token=token_row.refresh_token,
        token_expires_at=token_row.expires_at,
        on_token_refresh=_save,
    )


async def _fetch_orders(client: BlingClient, date_from: str, date_to: str) -> List[Dict[str, Any]]:
    """Fetch pedidos/vendas from Bling for a date range; returns [] on error."""
    try:
        resp = await client.get(
            "/pedidos/vendas",
            params={
                "dataInicial": date_from,
                "dataFinal": date_to,
                "pagina": 1,
                "limite": 100,
            },
        )
        data = resp.get("data", [])
        return data if isinstance(data, list) else []
    except BlingAuthError:
        raise
    except Exception as exc:
        logger.warning("dashboard._fetch_orders failed: %s", exc)
        return []


async def _fetch_low_stock(client: BlingClient) -> int:
    """Return count of products flagged with low stock in Bling."""
    try:
        resp = await client.get(
            "/produtos",
            params={"estoque": "S", "situacao": "A", "pagina": 1, "limite": 1},
        )
        # Bling wraps total count in meta when listing
        meta = resp.get("meta", {}) or {}
        total = meta.get("total", 0)
        # Some API versions put it directly in data
        if not total:
            total = len(resp.get("data", []))
        return int(total)
    except Exception as exc:
        logger.warning("dashboard._fetch_low_stock failed: %s", exc)
        return 0

# --------------------------------------------------------------------------- #
#  route
# --------------------------------------------------------------------------- #

@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Returns aggregated indicators for the home dashboard.

    - total_sold_today / total_sold_month: sum of Bling order values
    - orders_today / pending_orders: counts from Bling /pedidos/vendas
    - low_stock_products: products with low stock flag in Bling
    - recent_orders: last 10 orders
    - has_bling_auth: whether Bling OAuth2 token is configured
    """
    today = date.today()
    month_start = today.replace(day=1)
    date_today_str = today.strftime("%Y-%m-%d")
    date_month_str = month_start.strftime("%Y-%m-%d")

    client = _make_client(db)
    has_auth = client is not None

    # Defaults (shown when Bling is not connected)
    total_sold_today = 0.0
    total_sold_month = 0.0
    orders_today = 0
    pending_orders = 0
    low_stock_products = 0
    recent_orders: List[Dict[str, Any]] = []

    if has_auth:
        try:
            # Orders today
            today_orders = await _fetch_orders(client, date_today_str, date_today_str)
            orders_today = len(today_orders)
            total_sold_today = sum(
                float(o.get("totalProdutos") or o.get("total") or 0)
                for o in today_orders
            )
            pending_orders = sum(
                1 for o in today_orders
                if str(o.get("situacao", {}).get("id") if isinstance(o.get("situacao"), dict) else o.get("situacaoId", "")).strip()
                in ("6", "9", "15")  # Bling: 6=Em aberto, 9=Em andamento, 15=Pendente
            )

            # Orders this month (for total sold)
            month_orders = await _fetch_orders(client, date_month_str, date_today_str)
            total_sold_month = sum(
                float(o.get("totalProdutos") or o.get("total") or 0)
                for o in month_orders
            )

            # Low stock
            low_stock_products = await _fetch_low_stock(client)

            # Recent orders (last 10 from month list)
            for o in month_orders[:10]:
                situacao = o.get("situacao") or {}
                nome_contato = o.get("contato", {}).get("nome") or o.get("nomeCliente") or "—"
                recent_orders.append({
                    "id": o.get("id"),
                    "numero": o.get("numero"),
                    "data": o.get("data"),
                    "cliente": nome_contato,
                    "total": float(o.get("totalProdutos") or o.get("total") or 0),
                    "situacao": situacao.get("nome") if isinstance(situacao, dict) else str(situacao),
                })
        except BlingAuthError:
            has_auth = False
        except Exception as exc:
            logger.error("dashboard.summary error: %s", exc)

    return {
        "has_bling_auth": has_auth,
        "total_sold_today": total_sold_today,
        "total_sold_month": total_sold_month,
        "orders_today": orders_today,
        "pending_orders": pending_orders,
        "low_stock_products": low_stock_products,
        "recent_orders": recent_orders,
    }
