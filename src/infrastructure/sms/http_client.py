from typing import Optional
import httpx
from src.domain.entities import PhoneConfig


class PhoneHttpClient:
    def __init__(self, config: PhoneConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_ms / 1000.0),
            )
        return self._client

    async def health_check(self) -> tuple[bool, str]:
        try:
            client = await self._get_client()
            resp = await client.get("/health")
            if resp.status_code == 200:
                data = resp.json()
                return True, data.get("status", "ok")
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def send_sms(self, phone: str, text: str) -> tuple[bool, str]:
        try:
            client = await self._get_client()
            headers = {"X-API-Token": self.config.api_token} if self.config.api_token else {}
            resp = await client.post(
                "/send",
                json={"phone": phone, "text": text},
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return True, data.get("message_id", "")
                return False, data.get("error", "فشل الإرسال من الهاتف")
            return False, f"HTTP {resp.status_code}: {resp.text}"
        except httpx.TimeoutException:
            return False, "انتهت مهلة الاتصال بالهاتف"
        except httpx.ConnectError:
            return False, "تعذر الاتصال بالهاتف - تأكد من توصيل الجهاز"
        except Exception as e:
            return False, str(e)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
