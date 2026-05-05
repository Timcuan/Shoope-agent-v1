from unittest.mock import patch

import pytest
from curl_cffi.requests import Response

from shopee_agent.providers.shopee.client import ShopeeClient


@pytest.mark.asyncio
@patch("curl_cffi.requests.AsyncSession.request")
async def test_shopee_client_get(mock_request) -> None:
    # curl_cffi Response needs status_code and json support. We can mock it simply.
    class MockResponse:
        def __init__(self, data):
            self._data = data
        def json(self): return self._data
        def raise_for_status(self): pass
        
    mock_request.return_value = MockResponse({"response": {"shop_name": "Test"}})

    
    client = ShopeeClient(
        base_url="https://test.com",
        partner_id="123",
        partner_key="abc",
    )
    
    result = await client.get("/test_path", access_token="token", shop_id="456")
    
    assert result["response"]["shop_name"] == "Test"
    mock_request.assert_called_once()
    
    args, kwargs = mock_request.call_args
    assert args[0] == "GET"
    assert kwargs["url"] == "/test_path"
    assert kwargs["params"]["partner_id"] == "123"
    assert kwargs["params"]["access_token"] == "token"
    assert kwargs["params"]["shop_id"] == "456"
    assert "sign" in kwargs["params"]
    assert "timestamp" in kwargs["params"]


@pytest.mark.asyncio
@patch("curl_cffi.requests.AsyncSession.request")
async def test_shopee_client_post(mock_request) -> None:
    class MockResponse:
        def __init__(self, data):
            self._data = data
        def json(self): return self._data
        def raise_for_status(self): pass
        
    mock_request.return_value = MockResponse({"access_token": "new_token"})
    
    client = ShopeeClient(
        base_url="https://test.com",
        partner_id="123",
        partner_key="abc",
    )
    
    result = await client.post("/test_post", json_data={"code": "auth_code"})
    
    assert result["access_token"] == "new_token"
    mock_request.assert_called_once()
    
    args, kwargs = mock_request.call_args
    assert args[0] == "POST"
    assert kwargs["url"] == "/test_post"
    assert kwargs["json"]["code"] == "auth_code"
