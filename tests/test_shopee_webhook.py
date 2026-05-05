import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import json
from shopee_agent.entrypoints.api.main import app, verify_shopee_signature
from shopee_agent.config.settings import Settings

client = TestClient(app)

def generate_signature(url: str, body: dict, partner_key: str) -> str:
    body_bytes = json.dumps(body).encode('utf-8')
    base_string = f"{url}|{body_bytes.decode('utf-8')}"
    return hmac.new(
        partner_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_signature_verification_success():
    url = "https://example.com/events/webhook"
    body_dict = {"code": 1, "shop_id": "test_shop"}
    body_bytes = json.dumps(body_dict).encode('utf-8')
    partner_key = "test_key"
    
    signature = generate_signature(url, body_dict, partner_key)
    
    assert verify_shopee_signature(url, body_bytes, partner_key, signature) is True

def test_signature_verification_failure():
    url = "https://example.com/events/webhook"
    body_bytes = b'{"code": 1}'
    partner_key = "test_key"
    
    assert verify_shopee_signature(url, body_bytes, partner_key, "invalid_signature") is False

def test_webhook_endpoint_missing_auth():
    response = client.post("/events/webhook", json={"code": 1})
    assert response.status_code == 401
    assert "Missing Authorization header" in response.text

def test_webhook_endpoint_invalid_auth():
    response = client.post("/events/webhook", json={"code": 1}, headers={"Authorization": "bad_sign"})
    assert response.status_code == 401
    assert "Invalid signature" in response.text

def test_webhook_endpoint_success(monkeypatch):
    # Mock settings to have a known key
    monkeypatch.setenv("SHOPEE_PARTNER_KEY", "test_key")
    # Reload settings if needed, but TestClient might have already instantiated it
    # We will just patch the verify_shopee_signature directly for the endpoint test to avoid url matching issues
    
    from shopee_agent.entrypoints.api import main
    monkeypatch.setattr(main, "verify_shopee_signature", lambda u, b, k, s: True)
    
    payload = {
        "code": 1,
        "shop_id": "shop-webhook-1",
        "data": {
            "ordersn": "WEBHOOK_ORD_1"
        }
    }
    
    response = client.post(
        "/events/webhook", 
        json=payload, 
        headers={"Authorization": "valid_signature_mocked"}
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    
    # We could also verify the DB state, but this basic E2E confirms the route works and doesn't crash.
