import uuid

from fastapi.testclient import TestClient

from shopee_agent.entrypoints.api.main import app


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_simulator_event_ingest() -> None:
    client = TestClient(app)

    # Use unique order_sn per test run to avoid duplicate-key false negatives
    unique_order_sn = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    response = client.post(
        "/events/simulator",
        json={"event_type": "order.created", "shop_id": "shop-1", "order_sn": unique_order_sn},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["decision"]["recommended_action"] == "record_order"
