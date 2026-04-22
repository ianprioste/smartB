"""Behavior tests for strict planned deletions in plan execution."""

import asyncio

from app.api import plan_execution
from app.api import plans as plans_api


class _FakeHttpClient:
    async def aclose(self):
        return None


class _FakeBlingClient:
    def __init__(self, parent_sku: str, parent_id: int, variation_code: str, variation_id: int):
        self.parent_sku = parent_sku
        self.parent_id = parent_id
        self.variation_code = variation_code
        self.variation_id = variation_id
        self.put_calls = []
        self.delete_calls = []
        self.client = _FakeHttpClient()

    async def get(self, path, params=None):
        if path == f"/produtos/{self.parent_id}":
            return {
                "data": {
                    "id": self.parent_id,
                    "codigo": self.parent_sku,
                    "variacoes": [
                        {
                            "id": self.variation_id,
                            "codigo": self.variation_code,
                            "formato": "E",
                            "variacao": {"nome": "Cor: Branca;Tamanho: P"},
                            "estrutura": {
                                "componentes": [
                                    {"produto": {"id": 10}, "quantidade": 1}
                                ]
                            },
                        }
                    ],
                }
            }
        raise AssertionError(f"Unexpected GET path: {path}")

    async def put(self, path, payload):
        self.put_calls.append((path, payload))
        return {"data": {"id": self.parent_id}}

    async def delete(self, path):
        self.delete_calls.append(path)
        return {"data": {"ok": True}}


def _base_plan(strict_planned_deletions: bool, planned_deletions):
    return {
        "options": {
            "stock_type": "virtual",
            "strict_planned_deletions": strict_planned_deletions,
        },
        "colors": [{"code": "BR", "name": "Branca"}],
        "items": [
            {
                "sku": "CAMTEST",
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "computed_payload_preview": {"nome": "Produto teste", "preco": 99.9},
                "planned_deletions": planned_deletions,
            }
        ],
    }


def test_execute_plan_strict_blocks_on_deletion_mismatch(monkeypatch):
    fake_client = _FakeBlingClient(
        parent_sku="CAMTEST",
        parent_id=200,
        variation_code="CAMTESTBRP",
        variation_id=301,
    )

    async def fake_get_bling_client(_db):
        return fake_client

    async def fake_check_bling_products_bulk(_client, _skus):
        return {"CAMTEST": {"id": 200, "codigo": "CAMTEST"}}

    monkeypatch.setattr(plan_execution, "_get_bling_client", fake_get_bling_client)
    monkeypatch.setattr(plans_api, "_check_bling_products_bulk", fake_check_bling_products_bulk)

    result = asyncio.run(
        plan_execution.execute_plan_direct(
            _base_plan(strict_planned_deletions=True, planned_deletions=["CAMTESTOWM"]),
            db=object(),
        )
    )

    assert result["summary"]["failed"] == 1
    item = result["results"][0]
    assert item["status"] == "failed"
    assert item["error"] == "Strict planned deletions mismatch"
    assert item["unexpected_removed_variations"] == ["CAMTESTBRP"]
    assert item["missing_planned_deletions"] == ["CAMTESTOWM"]
    assert fake_client.delete_calls == []
    assert fake_client.put_calls == []


def test_execute_plan_non_strict_allows_deletion_and_update(monkeypatch):
    fake_client = _FakeBlingClient(
        parent_sku="CAMTEST",
        parent_id=200,
        variation_code="CAMTESTBRP",
        variation_id=301,
    )

    async def fake_get_bling_client(_db):
        return fake_client

    async def fake_check_bling_products_bulk(_client, _skus):
        return {"CAMTEST": {"id": 200, "codigo": "CAMTEST"}}

    monkeypatch.setattr(plan_execution, "_get_bling_client", fake_get_bling_client)
    monkeypatch.setattr(plans_api, "_check_bling_products_bulk", fake_check_bling_products_bulk)

    result = asyncio.run(
        plan_execution.execute_plan_direct(
            _base_plan(strict_planned_deletions=False, planned_deletions=["CAMTESTBRP"]),
            db=object(),
        )
    )

    assert result["summary"]["success"] == 1
    item = result["results"][0]
    assert item["status"] == "success"
    assert item["removed_variations"] == ["CAMTESTBRP"]
    assert item["unexpected_removed_variations"] == []
    assert item["missing_planned_deletions"] == []
    assert fake_client.delete_calls == ["/produtos/301"]
    assert len(fake_client.put_calls) == 1


def test_execute_plan_rebuilds_orphan_composition_in_parent_update(monkeypatch):
    class _FakeClientWithOrphan:
        def __init__(self):
            self.client = _FakeHttpClient()
            self.put_calls = []

        async def get(self, path, params=None):
            if path == "/produtos/200":
                return {
                    "data": {
                        "id": 200,
                        "codigo": "CAMTEST",
                        "variacoes": [
                            {
                                "id": 301,
                                "codigo": "CAMTESTBRP",
                                "formato": "E",
                                "variacao": {"nome": "Cor: Branca;Tamanho: P", "ordem": 1},
                                "estrutura": {"componentes": []},
                            }
                        ],
                    }
                }
            raise AssertionError(f"Unexpected GET path: {path}")

        async def put(self, path, payload):
            self.put_calls.append((path, payload))
            return {"data": {"id": 200}}

        async def delete(self, path):
            raise AssertionError(f"Unexpected DELETE path: {path}")

    fake_client = _FakeClientWithOrphan()

    async def fake_get_bling_client(_db):
        return fake_client

    async def fake_check_bling_products_bulk(_client, _skus):
        return {
            "CAMTEST": {"id": 200, "codigo": "CAMTEST"},
            "CAMBASEBRP": {"id": 999, "codigo": "CAMBASEBRP"},
        }

    async def fake_sync_snapshot(*args, **kwargs):
        return None

    monkeypatch.setattr(plan_execution, "_get_bling_client", fake_get_bling_client)
    monkeypatch.setattr(plan_execution, "_sync_snapshot_with_kind", fake_sync_snapshot)
    monkeypatch.setattr(plans_api, "_check_bling_products_bulk", fake_check_bling_products_bulk)

    plan = {
        "options": {"stock_type": "virtual"},
        "colors": [{"code": "BR", "name": "Branca"}],
        "items": [
            {
                "sku": "CAMTEST",
                "entity": "PARENT_PRINTED",
                "action": "UPDATE",
                "computed_payload_preview": {"nome": "Produto teste", "preco": 99.9},
            },
            {
                "sku": "CAMTESTBRP",
                "entity": "VARIATION_PRINTED",
                "action": "UPDATE",
                "hard_dependencies": ["CAMTEST", "CAMBASEBRP"],
                "computed_payload_preview": {"nome": "Produto teste BR P", "preco": 99.9, "variacao": {"ordem": 1}},
            },
        ],
    }

    result = asyncio.run(plan_execution.execute_plan_direct(plan, db=object()))

    assert result["summary"]["success"] == 1
    assert result["summary"]["repaired_orphan_compositions"] == ["CAMTESTBRP"]
    parent_result = next(r for r in result["results"] if r["sku"] == "CAMTEST")
    assert parent_result["repaired_orphan_compositions"] == ["CAMTESTBRP"]
    assert parent_result["repair_action"] == "orphan_composition_rebuilt"
    assert parent_result["dropped_orphan_compositions"] == []
    assert len(fake_client.put_calls) == 1
    _, put_payload = fake_client.put_calls[0]
    assert put_payload["variacoes"][0]["estrutura"]["componentes"] == [{"produto": {"id": 999}, "quantidade": 1}]
