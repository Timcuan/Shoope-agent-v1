import pytest
from datetime import datetime, timedelta
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.persistence.repositories import ShopTokenRepository, ShopTokenData

class MockClient:
    def __init__(self):
        self.partner_id = "123"
        self.post_called = 0
        self.get_called = 0

    async def post(self, path, json_data):
        self.post_called += 1
        return {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expire_in": 3600
        }
        
    async def get(self, path, access_token, shop_id, params=None):
        self.get_called += 1
        return {"response": {"shop_name": "Resilient Shop"}}

@pytest.mark.asyncio
async def test_shopee_gateway_auto_refresh(db_session):
    repo = ShopTokenRepository(db_session)
    # Token expiring in 5 minutes
    expiry = datetime.now() + timedelta(minutes=5)
    repo.upsert_token(ShopTokenData("12345", "old_access", "old_refresh", expiry))
    
    mock_client = MockClient()
    gateway = ShopeeGateway(mock_client, repo)
    
    # This should trigger auto-refresh before the call
    info = await gateway.get_shop_info("12345")
    
    assert mock_client.post_called == 1
    assert mock_client.get_called == 1
    
    # Verify DB has new token
    new_token = repo.get_token("12345")
    assert new_token.access_token == "new_access"
    assert new_token.expires_at > datetime.now() + timedelta(minutes=50)
