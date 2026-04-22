from app.api.events import _resolve_campaign_status_from_normalized
from app.api.orders import _resolve_order_target_status


def test_order_target_status_all_cancelled_maps_to_cancelado():
    key, label = _resolve_order_target_status(["cancelado", "cancelado"], has_frete=False)
    assert key == "cancelado"
    assert label == "Cancelado"


def test_order_target_status_mixed_cancelled_and_pending_stays_open():
    key, label = _resolve_order_target_status(["cancelado", "pendente"], has_frete=False)
    assert key == "em_aberto"
    assert label == "Em aberto"


def test_campaign_status_all_cancelled_maps_to_cancelado():
    key, label = _resolve_campaign_status_from_normalized(["cancelado", "cancelado"], has_frete=True)
    assert key == "cancelado"
    assert label == "Cancelado"


def test_campaign_status_mixed_cancelled_and_pending_stays_open():
    key, label = _resolve_campaign_status_from_normalized(["cancelado", "pendente"], has_frete=True)
    assert key == "em_aberto"
    assert label == "Em aberto"


def test_order_target_status_cancelled_and_rest_delivered_maps_to_atendido():
    key, label = _resolve_order_target_status(["cancelado", "entregue", "entregue"], has_frete=False)
    assert key == "atendido"
    assert label == "Atendido"


def test_order_target_status_cancelled_and_rest_packed_maps_to_ready_by_shipping():
    key_shipping, label_shipping = _resolve_order_target_status(["cancelado", "embalado", "embalado"], has_frete=True)
    assert key_shipping == "pronto_envio"
    assert label_shipping == "Pronto para envio"

    key_pickup, label_pickup = _resolve_order_target_status(["cancelado", "embalado", "embalado"], has_frete=False)
    assert key_pickup == "pronto_retirada"
    assert label_pickup == "Pronto para retirada"


def test_campaign_status_cancelled_and_rest_delivered_maps_to_atendido():
    key, label = _resolve_campaign_status_from_normalized(["cancelado", "entregue", "entregue"], has_frete=True)
    assert key == "atendido"
    assert label == "Atendido"


def test_campaign_status_cancelled_and_rest_packed_maps_to_ready_by_shipping():
    key_shipping, label_shipping = _resolve_campaign_status_from_normalized(["cancelado", "embalado", "embalado"], has_frete=True)
    assert key_shipping == "pronto_envio"
    assert label_shipping == "Pronto para envio"

    key_pickup, label_pickup = _resolve_campaign_status_from_normalized(["cancelado", "embalado", "embalado"], has_frete=False)
    assert key_pickup == "pronto_retirada"
    assert label_pickup == "Pronto para retirada"
