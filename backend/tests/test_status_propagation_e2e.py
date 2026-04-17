import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import events
from app.api import orders
from app.domain.status_propagation import StatusPropagationService
from app.models.database import (
    Base,
    ItemProductionNoteModel,
    SalesEventModel,
    TenantModel,
)
from app.models.schemas import ItemProductionNoteUpdateRequest


DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture()
def db_ctx():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    event_id = uuid.uuid4()
    try:
        db.add(TenantModel(id=DEFAULT_TENANT_ID, name="Default"))
        db.add(
            SalesEventModel(
                id=event_id,
                tenant_id=DEFAULT_TENANT_ID,
                name="E2E Status Propagation",
                start_date=date.today(),
                end_date=date.today(),
            )
        )
        db.commit()
        yield db, event_id
    finally:
        db.close()


def _seed_parent_children(db, event_id, order_id=101):
    parent = ItemProductionNoteModel(
        tenant_id=DEFAULT_TENANT_ID,
        event_id=event_id,
        sku="SKU-PAI",
        bling_order_id=order_id,
        production_status="Pendente",
        notes=None,
        is_parent=True,
        parent_sku=None,
    )
    child_a = ItemProductionNoteModel(
        tenant_id=DEFAULT_TENANT_ID,
        event_id=event_id,
        sku="SKU-FILHO-A",
        bling_order_id=order_id,
        production_status="Pendente",
        notes=None,
        is_parent=False,
        parent_sku="SKU-PAI",
    )
    child_b = ItemProductionNoteModel(
        tenant_id=DEFAULT_TENANT_ID,
        event_id=event_id,
        sku="SKU-FILHO-B",
        bling_order_id=order_id,
        production_status="Pendente",
        notes=None,
        is_parent=False,
        parent_sku="SKU-PAI",
    )
    db.add_all([parent, child_a, child_b])
    db.commit()


def test_service_parent_change_propagates_to_children(db_ctx):
    db, event_id = db_ctx
    _seed_parent_children(db, event_id, order_id=201)

    updated = StatusPropagationService.propagate_status_to_children(
        db=db,
        event_id=event_id,
        parent_sku="SKU-PAI",
        new_status="Em produção",
        bling_order_id=201,
    )

    assert len(updated) == 2

    children = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.parent_sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 201,
        )
        .all()
    )
    assert all(c.production_status == "Em produção" for c in children)


@pytest.mark.asyncio
async def test_endpoint_parent_change_propagates_to_children(db_ctx):
    db, event_id = db_ctx
    _seed_parent_children(db, event_id, order_id=301)

    body = ItemProductionNoteUpdateRequest(
        production_status="Em produção",
        notes="Aplicado no pai",
        bling_order_id=301,
    )

    response = await events.update_item_production(
        event_id=event_id,
        sku="SKU-PAI",
        body=body,
        db=db,
    )

    assert response.sku == "SKU-PAI"
    assert response.production_status == "Em produção"

    children = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.parent_sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 301,
        )
        .all()
    )
    assert all(c.production_status == "Em produção" for c in children)


@pytest.mark.asyncio
async def test_endpoint_children_equal_syncs_parent(db_ctx):
    db, event_id = db_ctx
    _seed_parent_children(db, event_id, order_id=401)

    first_child = ItemProductionNoteUpdateRequest(
        production_status="Em produção",
        notes=None,
        bling_order_id=401,
    )
    await events.update_item_production(
        event_id=event_id,
        sku="SKU-FILHO-A",
        body=first_child,
        db=db,
    )

    parent = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 401,
        )
        .first()
    )
    assert parent.production_status == "Pendente"

    second_child = ItemProductionNoteUpdateRequest(
        production_status="Em produção",
        notes=None,
        bling_order_id=401,
    )
    await events.update_item_production(
        event_id=event_id,
        sku="SKU-FILHO-B",
        body=second_child,
        db=db,
    )

    parent = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 401,
        )
        .first()
    )
    assert parent.production_status == "Em produção"


@pytest.mark.asyncio
async def test_endpoint_children_mixed_keeps_parent_status(db_ctx):
    db, event_id = db_ctx
    _seed_parent_children(db, event_id, order_id=501)

    child_a = ItemProductionNoteUpdateRequest(
        production_status="Em produção",
        notes=None,
        bling_order_id=501,
    )
    await events.update_item_production(
        event_id=event_id,
        sku="SKU-FILHO-A",
        body=child_a,
        db=db,
    )

    parent = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 501,
        )
        .first()
    )
    assert parent.production_status == "Pendente"

    child_b = ItemProductionNoteUpdateRequest(
        production_status="Produzido",
        notes=None,
        bling_order_id=501,
    )
    await events.update_item_production(
        event_id=event_id,
        sku="SKU-FILHO-B",
        body=child_b,
        db=db,
    )

    parent = (
        db.query(ItemProductionNoteModel)
        .filter(
            ItemProductionNoteModel.event_id == event_id,
            ItemProductionNoteModel.sku == "SKU-PAI",
            ItemProductionNoteModel.bling_order_id == 501,
        )
        .first()
    )
    assert parent.production_status == "Pendente"


@pytest.mark.asyncio
async def test_event_status_update_preserves_existing_notes_when_notes_omitted(db_ctx):
    db, event_id = db_ctx
    db.add(
        ItemProductionNoteModel(
            tenant_id=DEFAULT_TENANT_ID,
            event_id=event_id,
            sku="SKU-NOTA",
            bling_order_id=601,
            production_status="Pendente",
            notes="manter esta nota",
        )
    )
    db.commit()

    body = ItemProductionNoteUpdateRequest(
        production_status="Em produção",
        bling_order_id=601,
    )

    response = await events.update_item_production(
        event_id=event_id,
        sku="SKU-NOTA",
        body=body,
        db=db,
    )

    assert response.production_status == "Em produção"
    assert response.notes == "manter esta nota"


@pytest.mark.asyncio
async def test_orders_status_update_preserves_existing_notes_when_notes_omitted(db_ctx):
    db, event_id = db_ctx
    db.add(
        ItemProductionNoteModel(
            tenant_id=DEFAULT_TENANT_ID,
            event_id=event_id,
            sku="SKU-ORDERS",
            bling_order_id=None,
            production_status="Pendente",
            notes="nota global",
        )
    )
    db.commit()

    body = ItemProductionNoteUpdateRequest(production_status="Produzido")

    response = await orders.update_order_item_production(
        sku="SKU-ORDERS",
        body=body,
        db=db,
    )

    assert response.production_status == "Produzido"
    assert response.notes == "nota global"
