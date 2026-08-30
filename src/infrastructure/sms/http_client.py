import asyncio
from typing import Optional

import httpx

from src.domain.entities import PhoneConfig
from src.infrastructure.sms.device_detector import (
    detect_android_usb,
    detect_usb_tethering_gateway,
)


class PhoneHttpClient:
    HEALTH_TIMEOUT_SECONDS = 1.5

    def __init__(self, config: PhoneConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_ms / 1000.0, connect=2.0),
            )
        return self._client

    async def _probe_health(self, base_url: Optional[str] = None) -> tuple[bool, str]:
        timeout = httpx.Timeout(self.HEALTH_TIMEOUT_SECONDS, connect=1.0)
        try:
            if base_url is None:
                client = await self._get_client()
                resp = await client.get("/health", timeout=timeout)
            else:
                async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
                    resp = await client.get("/health")

            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"
            data = resp.json()
            status = str(data.get("status", "ok"))
            return status.lower() == "connected", status
        except httpx.ConnectTimeout:
            return False, "انتهت مهلة الوصول لخدمة الإرسال"
        except httpx.ConnectError:
            return False, "خدمة الإرسال غير متصلة"
        except httpx.TimeoutException:
            return False, "انتهت مهلة خدمة الإرسال"
        except Exception as exc:
            return False, str(exc)

    async def _switch_to_gateway(self, gateway: str) -> None:
        if not gateway or gateway == self.config.ip_address:
            return
        await self.close()
        self.config.ip_address = gateway

    async def health_check(self) -> tuple[bool, str]:
        """Quickly detect the Android device, tethering IP, and SMS service."""
        usb_task = asyncio.create_task(
            asyncio.to_thread(detect_android_usb, self.HEALTH_TIMEOUT_SECONDS)
        )
        gateway_task = asyncio.create_task(
            asyncio.to_thread(detect_usb_tethering_gateway, self.HEALTH_TIMEOUT_SECONDS)
        )
        configured_probe = asyncio.create_task(self._probe_health())

        configured_ok, configured_status = await configured_probe
        if configured_ok:
            return True, "connected"

        try:
            usb_found, device_name = await usb_task
        except Exception:
            usb_found, device_name = False, ""

        try:
            gateway = await gateway_task
        except Exception:
            gateway = ""

        gateway_status = ""
        if gateway and gateway != self.config.ip_address:
            gateway_ok, gateway_status = await self._probe_health(
                f"http://{gateway}:{self.config.port}"
            )
            if gateway_ok:
                await self._switch_to_gateway(gateway)
                return True, "connected"

        service_status = gateway_status or configured_status
        if usb_found:
            label = f" ({device_name})" if device_name else ""
            if gateway:
                return True, (
                    f"تم العثور على هاتف Android موصول{label} وعنوانه {gateway}، "
                    f"لكن خدمة الإرسال غير جاهزة: {service_status}"
                )
            return True, (
                f"تم العثور على هاتف Android موصول{label}، "
                "لكن USB Tethering أو خدمة الإرسال غير جاهزة"
            )

        if gateway:
            return True, (
                f"تم العثور على اتصال USB Tethering بعنوان {gateway}، "
                f"لكن خدمة الإرسال غير جاهزة: {service_status}"
            )

        return False, "لم يتم العثور على هاتف Android موصول أو USB Tethering فعال"

    async def _post_sms(self, base_url: Optional[str], phone: str, text: str):
        headers = {"X-API-Token": self.config.api_token} if self.config.api_token else {}
        request_timeout = httpx.Timeout(
            self.config.timeout_ms / 1000.0,
            connect=2.0,
        )
        if base_url is None:
            client = await self._get_client()
            return await client.post(
                "/send",
                json={"phone": phone, "text": text},
                headers=headers,
                timeout=request_timeout,
            )

        async with httpx.AsyncClient(base_url=base_url, timeout=request_timeout) as client:
            return await client.post(
                "/send",
                json={"phone": phone, "text": text},
                headers=headers,
            )

    @staticmethod
    def _parse_send_response(resp: httpx.Response) -> tuple[bool, str]:
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return True, data.get("message_id", "")
            return False, data.get("error", "فشل الإرسال من الهاتف")
        return False, f"HTTP {resp.status_code}: {resp.text}"

    async def send_sms(self, phone: str, text: str) -> tuple[bool, str]:
        try:
            resp = await self._post_sms(None, phone, text)
            return self._parse_send_response(resp)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            gateway = await asyncio.to_thread(detect_usb_tethering_gateway, 1.5)
            if gateway and gateway != self.config.ip_address:
                try:
                    resp = await self._post_sms(
                        f"http://{gateway}:{self.config.port}",
                        phone,
                        text,
                    )
                    result = self._parse_send_response(resp)
                    if result[0]:
                        await self._switch_to_gateway(gateway)
                    return result
                except httpx.TimeoutException:
                    return False, "انتهت مهلة الاتصال بخدمة الإرسال على الهاتف"
                except httpx.ConnectError:
                    pass
            return False, "تعذر الاتصال بخدمة الإرسال على الهاتف"
        except httpx.TimeoutException:
            return False, "انتهت مهلة الاتصال بالهاتف"
        except Exception as e:
            return False, str(e)

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
