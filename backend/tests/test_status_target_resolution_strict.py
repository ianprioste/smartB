from app.api.events import _resolve_bling_target_id_with_fallback as resolve_event_target
from app.api.orders import _resolve_bling_target_id_with_fallback as resolve_order_target


def test_orders_ready_status_does_not_fallback_to_open():
    sit_ids = {"em_aberto": 6, "atendido": 9, "cancelado": 12}
    assert resolve_order_target(sit_ids, "pronto_envio") is None
    assert resolve_order_target(sit_ids, "pronto_retirada") is None


def test_events_ready_status_does_not_fallback_to_open():
    sit_ids = {"em_aberto": 6, "atendido": 9, "cancelado": 12}
    assert resolve_event_target(sit_ids, "pronto_envio") is None
    assert resolve_event_target(sit_ids, "pronto_retirada") is None


def test_base_statuses_still_resolve_normally():
    sit_ids = {"em_aberto": 6, "atendido": 9, "cancelado": 12}
    assert resolve_order_target(sit_ids, "atendido") == 9
    assert resolve_order_target(sit_ids, "cancelado") == 12
    assert resolve_event_target(sit_ids, "atendido") == 9
    assert resolve_event_target(sit_ids, "cancelado") == 12
