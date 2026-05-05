import random
from curl_cffi.requests import AsyncSession, errors

from shopee_agent.providers.shopee.auth import generate_signature, generate_timestamp


class ShopeeClientError(Exception):
    pass

class ShopeeAuthError(ShopeeClientError):
    """Raised specifically when access_token is invalid or expired."""
    pass


class ShopeeClient:
    def __init__(self, base_url: str, partner_id: str, partner_key: str, proxy_url: str = "") -> None:
        self.base_url = base_url
        self.partner_id = partner_id
        self.partner_key = partner_key
        
        proxies = {"all": proxy_url} if proxy_url else None
        
        # TLS Profile Rotator
        profiles = ["chrome120", "chrome116", "edge116", "safari17_0", "safari15_3"]
        impersonate_target = random.choice(profiles)
        
        self.client = AsyncSession(base_url=self.base_url, proxies=proxies, impersonate=impersonate_target)

    async def get(
        self,
        path: str,
        access_token: str = "",
        shop_id: str = "",
        params: dict | None = None,
    ) -> dict:
        return await self._request("GET", path, access_token, shop_id, params=params)

    async def post(
        self,
        path: str,
        access_token: str = "",
        shop_id: str = "",
        json_data: dict | None = None,
    ) -> dict:
        return await self._request("POST", path, access_token, shop_id, json_data=json_data)

    async def _request(
        self,
        method: str,
        path: str,
        access_token: str,
        shop_id: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        # --- ANTI-BOT HARDENING: Human-like Pacing ---
        import asyncio
        import random
        # Random sleep before request to avoid rhythmic patterns
        await asyncio.sleep(random.uniform(0.1, 0.6))
        
        # --- ANTI-BOT HARDENING: Fingerprint Rotation ---
        profiles = ["chrome120", "chrome116", "edge116", "safari17_0", "safari15_3"]
        self.client.impersonate = random.choice(profiles)

        timestamp = generate_timestamp()
        sign = generate_signature(
            self.partner_key, self.partner_id, path, timestamp, access_token, shop_id
        )

        query = params.copy() if params else {}
        query.update(
            {
                "partner_id": self.partner_id,
                "timestamp": timestamp,
                "sign": sign,
            }
        )
        if access_token:
            query["access_token"] = access_token
        if shop_id:
            query["shop_id"] = shop_id

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.client.request(
                    method,
                    url=path,
                    params=query,
                    json=json_data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Sec-Fetch-Dest": "empty",
                        "Sec-Fetch-Mode": "cors",
                        "Sec-Fetch-Site": "cross-site",
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
                data = response.json()
                
                # Check for rate limiting specifically
                if data.get("error") == "error_too_many_request":
                    logger.warning(f"[Anti-Bot] Rate limit hit on {path}. Backing off...")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

                if data.get("error"):
                    # Don't retry auth errors here, but raise specific exception for Gateway to handle
                    if data.get("error") in ("error_auth", "error_token_invalid"):
                         raise ShopeeAuthError(f"Auth Error: {data.get('error')} - {data.get('message')}")
                    
                    if data.get("error") == "error_param":
                         raise ShopeeClientError(f"Param Error: {data.get('error')} - {data.get('message')}")
                    
                    if attempt < max_retries - 1:
                        jitter = random.uniform(0.5, 2.0)
                        await asyncio.sleep(2 * (attempt + 1) + jitter)
                        continue
                    raise ShopeeClientError(f"API Error: {data.get('error')} - {data.get('message')}")
                return data
            except errors.RequestsError as e:
                if attempt < max_retries - 1:
                    import asyncio
                    jitter = random.uniform(0.2, 1.5)
                    await asyncio.sleep(1 * (attempt + 1) + jitter)
                    continue
                raise ShopeeClientError(f"HTTP Error: {str(e)}") from e

    async def close(self) -> None:
        self.client.close()
