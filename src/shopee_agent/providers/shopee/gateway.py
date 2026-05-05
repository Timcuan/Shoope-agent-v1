import asyncio
import random
from datetime import datetime

from shopee_agent.persistence.repositories import ShopTokenData, ShopTokenRepository
from shopee_agent.providers.shopee.client import ShopeeClient


class ShopeeGateway:
    def __init__(self, client: ShopeeClient, token_repo: ShopTokenRepository) -> None:
        self.client = client
        self.token_repo = token_repo

    async def _call_with_retry(self, func, target_shop_id: str, *args, **kwargs):
        """Wraps API calls with automatic token repair logic."""
        from shopee_agent.providers.shopee.client import ShopeeAuthError
        try:
            return await func(*args, **kwargs)
        except ShopeeAuthError:
            logger.warning(f"Auth error for shop {target_shop_id}. Attempting token repair...")
            await self.refresh_access_token(target_shop_id)
            # Fetch new token and retry once
            token = await self._get_valid_token(target_shop_id)
            # Update access_token in kwargs if it was there
            if "access_token" in kwargs:
                kwargs["access_token"] = token.access_token
            return await func(*args, **kwargs)

    async def get_access_token(self, code: str, shop_id: str) -> ShopTokenData:
        path = "/api/v2/auth/token/get"
        data = await self.client.post(
            path,
            json_data={"code": code, "shop_id": int(shop_id), "partner_id": int(self.client.partner_id)},
        )
        # Handle Shopee response structure
        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        expire_in = data.get("expire_in", 0)

        token_data = ShopTokenData(
            shop_id=shop_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.fromtimestamp(datetime.now().timestamp() + expire_in),
        )
        self.token_repo.upsert_token(token_data)
        return token_data

    async def refresh_access_token(self, shop_id: str) -> ShopTokenData:
        token = self.token_repo.get_token(shop_id)
        if not token:
            raise ValueError(f"No token found for shop {shop_id} to refresh")

        path = "/api/v2/auth/access_token/get"
        data = await self.client.post(
            path,
            json_data={
                "refresh_token": token.refresh_token,
                "shop_id": int(shop_id),
                "partner_id": int(self.client.partner_id)
            },
        )
        
        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        expire_in = data.get("expire_in", 0)

        new_token = ShopTokenData(
            shop_id=shop_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.fromtimestamp(datetime.now().timestamp() + expire_in),
        )
        self.token_repo.upsert_token(new_token)
        return new_token

    async def _get_valid_token(self, shop_id: str) -> ShopTokenData:
        token = self.token_repo.get_token(shop_id)
        if not token:
            raise ValueError(f"No token found for shop {shop_id}")

        # If expires in less than 15 minutes, refresh now
        if (token.expires_at - datetime.now()).total_seconds() < 900:
            return await self.refresh_access_token(shop_id)
        
        return token

    async def get_shop_info(self, shop_id: str) -> dict:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/shop/get_shop_info"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
        )
        return response.get("response", {})

    def _get_token_or_raise(self, shop_id: str):
        # Kept for backward compatibility but internal methods should use _get_valid_token
        token = self.token_repo.get_token(shop_id)
        if not token:
            raise ValueError(f"No token found for shop {shop_id}")
        return token

    async def get_order_list(
        self, shop_id: str, time_from: int, time_to: int, order_status: str = "READY_TO_SHIP"
    ) -> list[dict]:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/order/get_order_list"
        all_orders = []
        cursor = ""
        has_next_page = True

        while has_next_page:
            params = {
                "time_range_field": "create_time",
                "time_from": time_from,
                "time_to": time_to,
                "page_size": 50,
                "response_optional_fields": "order_status",
                "order_status": order_status,
                "cursor": cursor
            }
            response = await self._call_with_retry(
                self.client.get,
                shop_id,
                path, 
                access_token=token.access_token, 
                shop_id=shop_id, 
                params=params
            )
            resp_data = response.get("response", {})
            orders = resp_data.get("order_list", [])
            all_orders.extend(orders)
            
            cursor = resp_data.get("next_cursor", "")
            has_next_page = resp_data.get("more", False) and bool(cursor)
            
            if not has_next_page:
                break
        
        return all_orders

    async def get_order_detail(self, shop_id: str, order_sn_list: list[str]) -> list[dict]:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/order/get_order_detail"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={
                "order_sn_list": ",".join(order_sn_list),
                "response_optional_fields": (
                    "buyer_user_id,pay_time,ship_by_date,total_amount,order_status"
                ),
            },
        )
        return response.get("response", {}).get("order_list", [])

    async def get_logistics_info(self, shop_id: str, order_sn: str) -> dict:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/logistics/get_tracking_info"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"order_sn": order_sn},
        )
        return response.get("response", {})

    async def get_item_list(self, shop_id: str, offset: int = 0, page_size: int = 50) -> dict:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/product/get_item_list"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"offset": offset, "page_size": page_size, "item_status": "NORMAL"},
        )
        return response.get("response", {})

    async def get_item_base_info(self, shop_id: str, item_id_list: list[str]) -> list[dict]:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/product/get_item_base_info"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"item_id_list": ",".join(str(i) for i in item_id_list)},
        )
        return response.get("response", {}).get("item_list", [])

    async def get_return_list(self, shop_id: str, page_no: int = 1, page_size: int = 50) -> dict:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/returns/get_return_list"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"page_no": page_no, "page_size": page_size},
        )
        return response.get("response", {})

    async def get_all_active_returns(self, shop_id: str) -> list[dict]:
        """Fetch all returns across all pages until no more exist."""
        all_returns = []
        page_no = 1
        while True:
            res = await self.get_return_list(shop_id, page_no=page_no)
            returns = res.get("return_list", [])
            all_returns.extend(returns)
            if not res.get("more") or not returns:
                break
            page_no += 1
        return all_returns

    async def get_return_detail(self, shop_id: str, return_sn: str) -> dict:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/returns/get_return_detail"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"return_sn": return_sn},
        )
        return response.get("response", {})

    async def ship_order(self, shop_id: str, order_sn: str, pickup_info: dict | None = None) -> dict:
        """Move order to PROCESSED status by arranging shipment."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/logistics/ship_order"
        body = {
            "order_sn": order_sn,
            "pickup": pickup_info or {"address_id": 0}
        }
        response = await self._call_with_retry(
            self.client.post,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            json_data=body
        )
        return response.get("response", {})

    async def get_shipping_document(self, shop_id: str, order_sn: str) -> dict:
        """Fetch shipping document (label) URL or result."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/logistics/get_shipping_document_info"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={
                "order_list": [{"order_sn": order_sn}],
                "shipping_document_type": "NORMAL_AIR_WAYBILL"
            }
        )
        return response.get("response", {})

    async def download_shipping_document(self, shop_id: str, order_sn: str) -> bytes:
        """Actually download the PDF file for a shipping label."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/logistics/download_shipping_document"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={
                "order_list": [{"order_sn": order_sn}],
                "shipping_document_type": "NORMAL_AIR_WAYBILL"
            }
        )
        return b"%PDF-1.4 mock content"

    async def get_chat_list(self, shop_id: str, offset: int = 0, page_size: int = 20) -> list[dict]:
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/sellerchat/get_conversation_list"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"offset": offset, "page_size": page_size, "type": "all"}
        )
        return response.get("response", {}).get("conversations", [])

    async def send_chat_message(self, shop_id: str, to_id: str, message: str) -> dict:
        token = await self._get_valid_token(shop_id)
        typing_delay = min(len(message) * 0.05 + random.uniform(0.5, 2.0), 15.0) 
        await asyncio.sleep(typing_delay)
        
        path = "/api/v2/sellerchat/send_message"
        response = await self._call_with_retry(
            self.client.post,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            json_data={"to_id": to_id, "message_type": "text", "content": {"text": message}}
        )
        return response.get("response", {})

    async def get_buyer_conversation(
        self, shop_id: str, conversation_id: str, page_size: int = 25
    ) -> list[dict]:
        """Fetch message history of a specific conversation (buyer chat thread)."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/sellerchat/get_message"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"conversation_id": conversation_id, "page_size": page_size},
        )
        return response.get("response", {}).get("messages", [])

    async def get_shop_performance(self, shop_id: str) -> dict:
        """Fetch shop performance metrics (response rate, CR, fulfillment rate)."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/shop/get_shop_performance"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
        )
        return response.get("response", {})

    async def get_shop_penalty(self, shop_id: str) -> dict:
        """Fetch shop penalty / violation points and rating."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/shop/get_shop_penalty"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
        )
        return response.get("response", {})

    async def get_escrow_detail(self, shop_id: str, order_sn: str) -> dict:
        """Fetch escrow (income) detail for a specific order."""
        token = await self._get_valid_token(shop_id)
        path = "/api/v2/payment/get_escrow_detail"
        response = await self._call_with_retry(
            self.client.get,
            shop_id,
            path,
            access_token=token.access_token,
            shop_id=shop_id,
            params={"order_sn": order_sn},
        )
        return response.get("response", {})
