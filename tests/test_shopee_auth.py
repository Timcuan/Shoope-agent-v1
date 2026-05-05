from unittest.mock import patch

from shopee_agent.providers.shopee.auth import generate_auth_url, generate_signature


def test_generate_signature() -> None:
    partner_key = "test_key"
    partner_id = "test_id"
    api_path = "/api/v2/test"
    timestamp = 1620000000

    # The expected base string is "test_id/api/v2/test1620000000"
    # hmac-sha256 of this string with "test_key"
    signature = generate_signature(partner_key, partner_id, api_path, timestamp)
    assert isinstance(signature, str)
    assert len(signature) == 64  # sha256 hex digest length


@patch("shopee_agent.providers.shopee.auth.generate_timestamp", return_value=1620000000)
def test_generate_auth_url(mock_time) -> None:
    url = generate_auth_url(
        base_url="https://partner.shopeemobile.com",
        partner_id="test_id",
        partner_key="test_key",
        redirect_url="http://localhost",
    )
    assert url.startswith("https://partner.shopeemobile.com/api/v2/shop/auth_partner")
    assert "partner_id=test_id" in url
    assert "timestamp=1620000000" in url
    assert "redirect=http://localhost" in url
    assert "sign=" in url
