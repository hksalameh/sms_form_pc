import asyncio
import logging
from typing import Optional
from src.domain.entities import PhoneConfig
from src.infrastructure.sms.http_client import PhoneHttpClient

logger = logging.getLogger(__name__)


class SmsSender:
    def __init__(self, config: Optional[PhoneConfig] = None):
        self._config = config or PhoneConfig()
        self._client: Optional[PhoneHttpClient] = None

    def _get_client(self) -> PhoneHttpClient:
        if self._client is None:
            self._client = PhoneHttpClient(self._config)
        return self._client

    async def send(self, phone: str, text: str) -> tuple[bool, str]:
        client = self._get_client()
        return await client.send_sms(phone, text)

    async def check_health(self) -> tuple[bool, str]:
        client = self._get_client()
        return await client.health_check()

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
