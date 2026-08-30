import asyncio
from typing import Optional

import httpx

from src.domain.entities import PhoneConfig
from src.infrastructure.sms.device_detector import detect_android_usb


class PhoneHttpClient:
    HEALTH_TIMEOUT_SECONDS = 1.5

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
        """Quickly check both Windows USB visibility and the SMS phone service."""
        usb_task = asyncio.create_task(
            asyncio.to_thread(detect_android_usb, self.HEALTH_TIMEOUT_SECONDS)
        )

        service_status = ""
        service_ok = False
        try:
            client = await self._get_client()
            timeout = httpx.Timeout(
                self.HEALTH_TIMEOUT_SECONDS,
                connect=1.0,
            )
            resp = await client.get("/health", timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                service_status = str(data.get("status", "ok"))
                service_ok = service_status.lower() == "connected"
            else:
                service_status = f"HTTP {resp.status_code}"
        except httpx.TimeoutException:
            service_status = "انتهت مهلة خدمة الإرسال"
        except httpx.ConnectError:
            service_status = "خدمة الإرسال غير متصلة"
        except Exception as exc:
            service_status = str(exc)

        try:
            usb_found, device_name = await usb_task
        except Exception:
            usb_found, device_name = False, ""

        if service_ok:
            if usb_found and device_name:
                return True, "connected"
            return True, "connected"

        if usb_found:
            label = f" ({device_name})" if device_name else ""
            return True, (
                f"تم العثور على هاتف Android موصول{label}، "
                f"لكن خدمة الإرسال غير جاهزة: {service_status}"
            )

        return False, (
            "لم يتم العثور على هاتف Android موصول، "
            f"وخدمة الإرسال غير متاحة: {service_status}"
        )

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
